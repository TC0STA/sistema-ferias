import re
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from routes import register_blueprints
from services.termination_service import TerminationService
from services.user_service import UserService


BASE_DIR = Path(__file__).resolve().parent.parent


class TerminationFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "usuarios.db"
        self.app = Flask(
            "fokus-termination-test",
            template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"),
        )
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret",
            USER_DATABASE_PATH=str(self.database_path),
        )
        register_blueprints(self.app)
        self.users: UserService = self.app.extensions["fokus_user_service"]
        self.terminations: TerminationService = self.app.extensions[
            "fokus_termination_service"
        ]
        self.rh = self.users.create(
            nome="Analista RH", usuario="rh.desligamentos",
            email="rh.desligamentos@fokus.local", senha="senha-segura", perfil="rh",
        )
        self.target = self.users.create(
            nome="Colaborador Alvo", usuario="colaborador.alvo",
            email="alvo@fokus.local", senha="senha-segura", perfil="consulta",
        )
        self.manager = self.users.create(
            nome="Gestor", usuario="gestor.desligamentos",
            email="gestor.desligamentos@fokus.local", senha="senha-segura", perfil="gestor",
        )
        self.viewer = self.users.create(
            nome="Consulta", usuario="consulta.desligamentos",
            email="consulta.desligamentos@fokus.local", senha="senha-segura", perfil="consulta",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    @staticmethod
    def _token(response) -> str:
        match = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        if match is None:
            raise AssertionError("Token CSRF não encontrado.")
        return match.group(1).decode()

    def _login(self, client, username: str, password: str = "senha-segura"):
        token = self._token(client.get("/login"))
        with patch("routes.auth.backend.registrar_auditoria"):
            response = client.post("/login", data={
                "usuario": username, "senha": password, "csrf_token": token,
            })
        self.assertEqual(response.status_code, 302)

    def _create_as_rh(self):
        client = self.app.test_client()
        self._login(client, self.rh.usuario)
        token = self._token(client.get("/desligamentos"))
        with patch("routes.desligamentos.backend.registrar_auditoria") as audit:
            response = client.post("/desligamentos/criar", data={
                "csrf_token": token,
                "user_id": str(self.target.id),
                "filial": "Matriz",
                "departamento": "Operações",
                "data_desligamento": date.today().isoformat(),
                "observacao": "Solicitação do RH",
            })
        self.assertEqual(response.status_code, 302)
        audit.assert_called_once()
        return client, self.terminations.list_all()[0]

    def _create_manual_request(self, *, username: str, email: str):
        return self.terminations.create(
            user_id=None,
            nome="Colaborador Manual",
            usuario=username,
            email=email,
            perfil="consulta",
            filial="Matriz",
            departamento="Operações",
            data_desligamento=date.today(),
            observacao="Sem associação inicial",
            solicitado_por_id=self.rh.id,
            solicitado_por=self.rh.nome,
        )

    def _confirm_as_admin(self, record, *, follow_redirects=False):
        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        token = self._token(admin.get("/desligamentos"))
        with patch("routes.desligamentos.backend.registrar_auditoria") as audit:
            response = admin.post(
                f"/desligamentos/{record.id}/confirmar",
                data={"csrf_token": token},
                follow_redirects=follow_redirects,
            )
        return response, audit

    def test_rh_creates_and_tracks_request_and_admin_can_view_it(self):
        rh_client, record = self._create_as_rh()
        admin_user = self.users.get_by_username("admin")
        self.terminations.create(
            user_id=None, nome="Outra Pessoa", usuario="outra.pessoa",
            email="outra@fokus.local", perfil="consulta", filial="Filial Norte",
            departamento="Comercial", data_desligamento=date.today(),
            observacao="Solicitação administrativa",
            solicitado_por_id=admin_user.id, solicitado_por=admin_user.nome,
        )
        self.assertEqual(record.status, "Pendente")
        self.assertEqual(record.user_id, self.target.id)
        rh_page = rh_client.get("/desligamentos").get_data(as_text=True)
        self.assertIn("Colaborador Alvo", rh_page)
        self.assertNotIn("Outra Pessoa", rh_page)

        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        page = admin.get("/desligamentos")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Colaborador Alvo", page.get_data(as_text=True))
        self.assertIn("Outra Pessoa", page.get_data(as_text=True))

    def test_dashboard_alert_is_visible_only_to_admin(self):
        rh_client, _ = self._create_as_rh()
        rh_dashboard = rh_client.get("/dashboard").get_data(as_text=True)
        self.assertNotIn("desligamento(s) pendente(s)", rh_dashboard)

        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        admin_dashboard = admin.get("/dashboard")
        self.assertEqual(admin_dashboard.status_code, 200)
        self.assertIn(
            "desligamento(s) pendente(s)", admin_dashboard.get_data(as_text=True)
        )

    def test_rh_cannot_confirm_deactivation(self):
        rh_client, record = self._create_as_rh()
        token = self._token(rh_client.get("/desligamentos"))
        response = rh_client.post(
            f"/desligamentos/{record.id}/confirmar",
            data={"csrf_token": token},
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(self.users.get_by_id(self.target.id).ativo)

    def test_manager_and_consultation_cannot_access_feature(self):
        for user in (self.manager, self.viewer):
            with self.subTest(profile=user.perfil):
                client = self.app.test_client()
                self._login(client, user.usuario)
                self.assertEqual(client.get("/desligamentos").status_code, 403)

    def test_admin_confirms_once_without_deleting_user_and_audits(self):
        _, record = self._create_as_rh()
        initial_count = self.users.count()
        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        token = self._token(admin.get("/desligamentos"))
        with patch("routes.desligamentos.backend.registrar_auditoria") as audit:
            response = admin.post(
                f"/desligamentos/{record.id}/confirmar",
                data={"csrf_token": token},
            )
        self.assertEqual(response.status_code, 302)
        audit.assert_called_once()
        target = self.users.get_by_id(self.target.id)
        self.assertIsNotNone(target)
        self.assertFalse(target.ativo)
        self.assertEqual(self.users.count(), initial_count)
        processed = self.terminations.get_by_id(record.id)
        self.assertEqual(processed.status, "Desativado")
        self.assertIsNotNone(processed.desativado_em)

        with patch("routes.desligamentos.backend.registrar_auditoria") as second_audit:
            second = admin.post(
                f"/desligamentos/{record.id}/confirmar",
                data={"csrf_token": self._token(admin.get('/desligamentos'))},
            )
        self.assertEqual(second.status_code, 302)
        second_audit.assert_not_called()
        self.assertEqual(self.terminations.get_by_id(record.id).status, "Desativado")

    def test_admin_confirms_without_user_id_by_exact_username(self):
        record = self._create_manual_request(
            username=self.target.usuario.upper(),
            email="email.diferente@fokus.local",
        )
        initial_count = self.users.count()
        response, audit = self._confirm_as_admin(record)

        self.assertEqual(response.status_code, 302)
        audit.assert_called_once()
        processed = self.terminations.get_by_id(record.id)
        self.assertEqual(processed.user_id, self.target.id)
        self.assertEqual(processed.status, "Desativado")
        self.assertFalse(self.users.get_by_id(self.target.id).ativo)
        self.assertEqual(self.users.count(), initial_count)

    def test_admin_confirms_without_user_id_by_exact_email_fallback(self):
        record = self._create_manual_request(
            username="usuario.inexistente",
            email=self.target.email.upper(),
        )
        response, audit = self._confirm_as_admin(record)

        self.assertEqual(response.status_code, 302)
        audit.assert_called_once()
        processed = self.terminations.get_by_id(record.id)
        self.assertEqual(processed.user_id, self.target.id)
        self.assertEqual(processed.status, "Desativado")
        self.assertFalse(self.users.get_by_id(self.target.id).ativo)

    def test_confirmation_blocks_when_user_is_not_found(self):
        record = self._create_manual_request(
            username="nao.existe", email="nao.existe@fokus.local"
        )
        response, audit = self._confirm_as_admin(record, follow_redirects=True)

        self.assertIn(
            "Usuário não encontrado no sistema. Verifique o usuário ou e-mail informado.",
            response.get_data(as_text=True),
        )
        audit.assert_not_called()
        pending = self.terminations.get_by_id(record.id)
        self.assertIsNone(pending.user_id)
        self.assertEqual(pending.status, "Pendente")

    def test_confirmation_blocks_multiple_exact_correspondences(self):
        other = self.users.create(
            nome="Outra Correspondência",
            usuario="outra.correspondencia",
            email="outra.correspondencia@fokus.local",
            senha="senha-segura",
            perfil="consulta",
        )
        record = self._create_manual_request(
            username=self.target.usuario,
            email=other.email,
        )
        response, audit = self._confirm_as_admin(record, follow_redirects=True)

        self.assertIn(
            "Existem múltiplos usuários correspondentes",
            response.get_data(as_text=True),
        )
        audit.assert_not_called()
        pending = self.terminations.get_by_id(record.id)
        self.assertIsNone(pending.user_id)
        self.assertEqual(pending.status, "Pendente")
        self.assertTrue(self.users.get_by_id(self.target.id).ativo)
        self.assertTrue(self.users.get_by_id(other.id).ativo)

    def test_cancelled_request_remains_in_history(self):
        _, record = self._create_as_rh()
        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        token = self._token(admin.get("/desligamentos"))
        with patch("routes.desligamentos.backend.registrar_auditoria") as audit:
            admin.post(
                f"/desligamentos/{record.id}/cancelar",
                data={"csrf_token": token},
            )
        audit.assert_called_once()
        cancelled = self.terminations.get_by_id(record.id)
        self.assertEqual(cancelled.status, "Cancelado")
        self.assertIn(cancelled.id, [item.id for item in self.terminations.list_all()])
        self.assertTrue(self.users.get_by_id(self.target.id).ativo)

    def test_admin_edits_pending_request_and_audits_change(self):
        _, record = self._create_as_rh()
        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        token = self._token(admin.get("/desligamentos"))
        with patch("routes.desligamentos.backend.registrar_auditoria") as audit:
            response = admin.post(
                f"/desligamentos/{record.id}/editar",
                data={
                    "csrf_token": token,
                    "user_id": str(self.target.id),
                    "filial": "Filial Sul",
                    "departamento": "Financeiro",
                    "data_desligamento": date.today().isoformat(),
                    "observacao": "Dados corrigidos",
                },
            )
        self.assertEqual(response.status_code, 302)
        audit.assert_called_once()
        edited = self.terminations.get_by_id(record.id)
        self.assertEqual(edited.filial, "Filial Sul")
        self.assertEqual(edited.departamento, "Financeiro")
        self.assertEqual(edited.status, "Pendente")

    def test_duplicate_pending_request_is_rejected(self):
        self._create_as_rh()
        with self.assertRaisesRegex(ValueError, "solicitação pendente"):
            self.terminations.create(
                user_id=self.target.id, nome=self.target.nome,
                usuario=self.target.usuario, email=self.target.email,
                perfil=self.target.perfil, filial="Matriz", departamento="Operações",
                data_desligamento=date.today(), observacao="Duplicada",
                solicitado_por_id=self.rh.id, solicitado_por=self.rh.nome,
            )
        self.assertEqual(len(self.terminations.list_all()), 1)

    def test_invalid_date_and_missing_identity_are_rejected(self):
        client = self.app.test_client()
        self._login(client, self.rh.usuario)
        token = self._token(client.get("/desligamentos"))
        response = client.post("/desligamentos/criar", data={
            "csrf_token": token, "nome": "", "usuario": "",
            "email": "invalido", "data_desligamento": "data-invalida",
        }, follow_redirects=True)
        self.assertIn("Nome e usuário são obrigatórios", response.get_data(as_text=True))
        self.assertEqual(self.terminations.count_pending(), 0)

        token = self._token(client.get("/desligamentos"))
        invalid_date = client.post("/desligamentos/criar", data={
            "csrf_token": token, "nome": "Pessoa Manual", "usuario": "manual",
            "email": "manual@fokus.local", "data_desligamento": "data-invalida",
        }, follow_redirects=True)
        self.assertIn(
            "data de desligamento válida", invalid_date.get_data(as_text=True)
        )
        self.assertEqual(self.terminations.count_pending(), 0)

    def test_already_inactive_user_is_not_processed_again(self):
        _, record = self._create_as_rh()
        self.users.set_active(self.target.id, False)
        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        token = self._token(admin.get("/desligamentos"))
        with patch.object(
            self.users, "set_active", wraps=self.users.set_active
        ) as set_active, patch(
            "routes.desligamentos.backend.registrar_auditoria"
        ) as audit:
            response = admin.post(
                f"/desligamentos/{record.id}/confirmar",
                data={"csrf_token": token}, follow_redirects=True,
            )
        self.assertIn("já estava inativo", response.get_data(as_text=True))
        set_active.assert_not_called()
        audit.assert_called_once()
        processed = self.terminations.get_by_id(record.id)
        self.assertEqual(processed.status, "Desativado")
        self.assertEqual(processed.user_id, self.target.id)
        self.assertIsNotNone(self.users.get_by_id(self.target.id))

    def test_records_persist_between_service_instances(self):
        _, created = self._create_as_rh()
        reopened = TerminationService(self.database_path).get_by_id(created.id)
        self.assertIsNotNone(reopened)
        self.assertEqual(reopened.usuario, self.target.usuario)
        self.assertEqual(reopened.status, "Pendente")


if __name__ == "__main__":
    unittest.main()
