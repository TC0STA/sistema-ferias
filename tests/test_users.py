import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from werkzeug.security import check_password_hash

from routes import register_blueprints
from services.user_service import UserService


BASE_DIR = Path(__file__).resolve().parent.parent


class UserAdministrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "usuarios.db"
        self.app = Flask(
            "fokus-users-test",
            template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"),
        )
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret",
            USER_DATABASE_PATH=str(self.database_path),
        )
        register_blueprints(self.app)
        self.client = self.app.test_client()
        self.users = UserService(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _csrf(self, client, path="/login"):
        response = client.get(path)
        token = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(token)
        return token.group(1).decode()

    def _login(self, client=None, username="admin", password="admin123"):
        client = client or self.client
        with patch("routes.auth.backend.registrar_auditoria"):
            return client.post(
                "/login",
                data={
                    "usuario": username,
                    "senha": password,
                    "csrf_token": self._csrf(client),
                },
            )

    def _admin_csrf(self):
        return self._csrf(self.client, "/usuarios")

    def test_only_admin_can_access_users_page_and_see_menu(self):
        self._login()
        response = self.client.get("/usuarios")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Administração de Usuários", response.get_data(as_text=True))
        self.assertIn('<span>Usuários</span>', response.get_data(as_text=True))

        for profile in ("rh", "gestor", "consulta"):
            with self.subTest(profile=profile):
                user = self.users.create(
                    nome=f"Usuário {profile}",
                    usuario=profile,
                    email=f"{profile}@fokus.local",
                    senha="senha-segura",
                    perfil=profile,
                )
                client = self.app.test_client()
                self._login(client, user.usuario, "senha-segura")
                forbidden = client.get("/usuarios")
                self.assertEqual(forbidden.status_code, 403)
                dashboard = client.get("/dashboard")
                self.assertNotIn('<span>Usuários</span>', dashboard.get_data(as_text=True))

    def test_admin_creates_user_with_hash_and_audit(self):
        self._login()
        with patch("routes.usuarios.backend.registrar_auditoria") as audit:
            response = self.client.post(
                "/usuarios/criar",
                data={
                    "nome": "Nova Usuária",
                    "usuario": "nova.usuario",
                    "email": "nova.usuario@fokus.local",
                    "senha": "senha-super-segura",
                    "confirmar_senha": "senha-super-segura",
                    "perfil": "rh",
                    "ativo": "1",
                    "csrf_token": self._admin_csrf(),
                },
                follow_redirects=True,
            )

        self.assertIn("criado com sucesso", response.get_data(as_text=True))
        created = self.users.get_by_username("nova.usuario")
        self.assertIsNotNone(created)
        self.assertNotEqual(created.senha_hash, "senha-super-segura")
        self.assertTrue(check_password_hash(created.senha_hash, "senha-super-segura"))
        audit.assert_called_once()
        self.assertEqual(audit.call_args.args[0], "Criação de usuário")
        self.assertEqual(audit.call_args.kwargs["usuario"], "Administrador")
        self.assertIn("nova.usuario", audit.call_args.args[1])

    def test_duplicate_username_and_email_are_rejected(self):
        self._login()
        self.users.create(
            nome="Usuário Existente",
            usuario="existente",
            email="existente@fokus.local",
            senha="senha-segura",
            perfil="consulta",
        )
        base_data = {
            "nome": "Duplicado",
            "senha": "outra-senha-segura",
            "confirmar_senha": "outra-senha-segura",
            "perfil": "consulta",
            "ativo": "1",
        }
        cases = (
            ("existente", "outro@fokus.local", "Este usuário já está cadastrado."),
            ("outro", "existente@fokus.local", "Este e-mail já está cadastrado."),
        )
        for username, email, message in cases:
            with self.subTest(message=message):
                response = self.client.post(
                    "/usuarios/criar",
                    data={
                        **base_data,
                        "usuario": username,
                        "email": email,
                        "csrf_token": self._admin_csrf(),
                    },
                    follow_redirects=True,
                )
                self.assertIn(message, response.get_data(as_text=True))
        self.assertEqual(self.users.count(), 2)

    def test_inactive_user_cannot_login(self):
        self.users.create(
            nome="Usuário Inativo",
            usuario="inativo",
            email="inativo@fokus.local",
            senha="senha-segura",
            perfil="consulta",
            ativo=False,
        )
        response = self._login(username="inativo", password="senha-segura")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Usuário ou senha inválidos.", response.get_data(as_text=True))
        with self.client.session_transaction() as browser_session:
            self.assertIsNone(browser_session.get("user_id"))

    def test_admin_cannot_deactivate_own_account(self):
        self._login()
        admin = self.users.get_by_username("admin")
        with patch("routes.usuarios.backend.registrar_auditoria") as audit:
            response = self.client.post(
                f"/usuarios/{admin.id}/status",
                data={"ativo": "0", "csrf_token": self._admin_csrf()},
                follow_redirects=True,
            )
        self.assertIn("Você não pode desativar a própria conta.", response.get_data(as_text=True))
        self.assertTrue(self.users.get_by_id(admin.id).ativo)
        audit.assert_not_called()

    def test_edit_status_and_password_reset_are_audited(self):
        target = self.users.create(
            nome="Usuária Alvo",
            usuario="alvo",
            email="alvo@fokus.local",
            senha="senha-inicial",
            perfil="consulta",
        )
        self._login()
        with patch("routes.usuarios.backend.registrar_auditoria") as audit:
            self.client.post(
                f"/usuarios/{target.id}/editar",
                data={
                    "nome": "Usuária Editada",
                    "email": "editada@fokus.local",
                    "perfil": "gestor",
                    "ativo": "0",
                    "csrf_token": self._admin_csrf(),
                },
            )
            self.client.post(
                f"/usuarios/{target.id}/status",
                data={"ativo": "1", "csrf_token": self._admin_csrf()},
            )
            self.client.post(
                f"/usuarios/{target.id}/redefinir-senha",
                data={
                    "senha": "senha-redefinida",
                    "confirmar_senha": "senha-redefinida",
                    "csrf_token": self._admin_csrf(),
                },
            )

        updated = self.users.get_by_id(target.id)
        self.assertEqual(updated.nome, "Usuária Editada")
        self.assertEqual(updated.perfil, "gestor")
        self.assertTrue(updated.ativo)
        self.assertNotEqual(updated.senha_hash, "senha-redefinida")
        self.assertTrue(check_password_hash(updated.senha_hash, "senha-redefinida"))
        actions = [call.args[0] for call in audit.call_args_list]
        self.assertEqual(actions, [
            "Edição de usuário",
            "Alteração de perfil",
            "Desativação de usuário",
            "Ativação de usuário",
            "Redefinição de senha",
        ])
        for call in audit.call_args_list:
            self.assertEqual(call.kwargs["usuario"], "Administrador")
            self.assertIn("alvo", call.args[1])


if __name__ == "__main__":
    unittest.main()
