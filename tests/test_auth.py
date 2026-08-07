import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from flask import Flask, render_template, session
from werkzeug.security import check_password_hash

from routes import register_blueprints
from services.auth_service import load_current_user
from services.user_service import UserService


BASE_DIR = Path(__file__).resolve().parent.parent


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "usuarios.db"
        self.app = Flask(
            "fokus-auth-test",
            template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static")
        )
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret",
            USER_DATABASE_PATH=str(self.database_path)
        )
        register_blueprints(self.app)
        self.client = self.app.test_client()
        self.users = UserService(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _csrf(self):
        response = self.client.get("/login")
        token = re.search(
            rb'name="csrf_token" value="([^"]+)"', response.data
        )
        self.assertIsNotNone(token)
        return token.group(1).decode()

    def _login(self, username="admin", password="admin123"):
        with patch("routes.auth.backend.registrar_auditoria"):
            return self.client.post(
                "/login",
                data={
                    "usuario": username,
                    "senha": password,
                    "csrf_token": self._csrf()
                }
            )

    def test_default_admin_uses_requested_schema_and_password_hash(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            columns = [
                row[1] for row in connection.execute(
                    "PRAGMA table_info(usuarios)"
                ).fetchall()
            ]
        self.assertEqual(columns, [
            "id", "nome", "usuario", "email", "senha_hash", "perfil",
            "ativo", "ultimo_login", "created_at"
        ])
        admin = self.users.get_by_username("admin")
        self.assertEqual(admin.perfil, "admin")
        self.assertNotEqual(admin.senha_hash, "admin123")
        self.assertTrue(check_password_hash(admin.senha_hash, "admin123"))

    def test_anonymous_requests_are_redirected_and_apis_return_401(self):
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login?next=", response.headers["Location"])
        response = self.client.get("/api/versao-dados")
        self.assertEqual(response.status_code, 401)

    def test_login_updates_session_and_last_login(self):
        response = self._login()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith("/dashboard"))
        with self.client.session_transaction() as browser_session:
            self.assertIsInstance(browser_session.get("user_id"), int)
        self.assertIsNotNone(self.users.get_by_username("admin").ultimo_login)

    def test_role_guard_blocks_forbidden_routes(self):
        self.users.create(
            nome="Usuário Consulta",
            usuario="consulta",
            email="consulta@fokus.local",
            senha="senha-segura",
            perfil="consulta"
        )
        self._login("consulta", "senha-segura")
        self.assertEqual(self.client.get("/configuracoes").status_code, 403)
        self.assertEqual(self.client.get("/api/importacao/plugins").status_code, 403)
        self.assertEqual(self.client.get("/api/versao-dados").status_code, 200)

    def test_sidebar_is_rendered_from_the_authenticated_profile(self):
        manager = self.users.create(
            nome="Gestora Fokus",
            usuario="gestora",
            email="gestora@fokus.local",
            senha="senha-segura",
            perfil="gestor"
        )
        with self.app.test_request_context("/dashboard"):
            session["user_id"] = manager.id
            load_current_user()
            html = render_template("_sidebar.html")
        self.assertIn("Dashboard", html)
        self.assertIn("Calendário", html)
        self.assertIn("Relatórios", html)
        self.assertNotIn("Importação", html)
        self.assertNotIn("Colaboradores", html)
        self.assertNotIn("Auditoria", html)
        self.assertNotIn("Configurações", html)


if __name__ == "__main__":
    unittest.main()
