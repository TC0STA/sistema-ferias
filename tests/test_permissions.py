import re
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from flask import Flask, render_template, session

from permissions import has_permission
from routes import register_blueprints
from services.auth_service import load_current_user
from services.user_service import UserService


BASE_DIR = Path(__file__).resolve().parent.parent


class ProfilePermissionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "usuarios.db"
        self.app = Flask(
            "fokus-permissions-test",
            template_folder=str(BASE_DIR / "templates"),
            static_folder=str(BASE_DIR / "static"),
        )
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret",
            USER_DATABASE_PATH=str(self.database_path),
        )
        register_blueprints(self.app)
        self.users = UserService(self.database_path)
        self.profile_users = {"admin": self.users.get_by_username("admin")}
        for profile in ("rh", "gestor", "consulta"):
            self.profile_users[profile] = self.users.create(
                nome=f"Perfil {profile}",
                usuario=profile,
                email=f"{profile}@fokus.local",
                senha="senha-segura",
                perfil=profile,
            )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _csrf(self, client):
        response = client.get("/login")
        token = re.search(rb'name="csrf_token" value="([^"]+)"', response.data)
        self.assertIsNotNone(token)
        return token.group(1).decode()

    def _client_for(self, profile):
        client = self.app.test_client()
        password = "admin123" if profile == "admin" else "senha-segura"
        with patch("routes.auth.backend.registrar_auditoria"):
            response = client.post(
                "/login",
                data={
                    "usuario": self.profile_users[profile].usuario,
                    "senha": password,
                    "csrf_token": self._csrf(client),
                },
            )
        self.assertEqual(response.status_code, 302)
        return client

    def _sidebar_for(self, profile):
        with self.app.test_request_context("/dashboard"):
            session["user_id"] = self.profile_users[profile].id
            load_current_user()
            return render_template("_sidebar.html")

    def _isolated_dashboard_routes(self):
        stack = ExitStack()
        stack.enter_context(patch("routes.auth.render_template", return_value="forbidden"))
        stack.enter_context(patch("routes.dashboard.render_template", return_value="ok"))
        stack.enter_context(patch(
            "routes.dashboard.obter_inteligencia_sistema", return_value={}
        ))
        stack.enter_context(patch(
            "routes.dashboard.obter_resumo_sistema", return_value={}
        ))
        stack.enter_context(patch(
            "routes.dashboard.obter_timeline_sistema", return_value=[]
        ))
        stack.enter_context(patch(
            "routes.dashboard.obter_saude_sistema", return_value=[]
        ))
        stack.enter_context(patch(
            "routes.dashboard.planilhas_importadas", return_value=[]
        ))
        stack.enter_context(patch(
            "routes.dashboard.planilha_mais_recente", return_value=None
        ))
        stack.enter_context(patch(
            "routes.dashboard._termination_pending_count", return_value=0
        ))
        return stack

    def test_permission_matrix(self):
        expected = {
            "admin": {
                "inteligencia", "dashboard", "importacao", "calendario", "colaboradores",
                "editar_colaboradores", "historico", "relatorios",
                "auditoria", "usuarios", "configuracoes", "pesquisa",
                "desligamentos",
            },
            "rh": {
                "dashboard", "importacao", "calendario", "colaboradores",
                "editar_colaboradores", "historico", "relatorios", "pesquisa",
                "desligamentos",
            },
            "gestor": {
                "dashboard", "calendario", "colaboradores", "relatorios",
                "pesquisa",
            },
            "consulta": {
                "dashboard", "calendario", "colaboradores", "relatorios",
                "pesquisa",
            },
        }
        permissions = set().union(*expected.values())
        for profile, allowed in expected.items():
            for permission in permissions:
                with self.subTest(profile=profile, permission=permission):
                    self.assertEqual(
                        has_permission(profile, permission),
                        permission in allowed,
                    )

    def test_sidebar_matches_each_profile(self):
        expected_links = {
            "admin": {
                "/", "/dashboard", "/importar", "/calendario", "/colaboradores",
                "/historico", "/relatorios", "/auditoria", "/usuarios",
                "/configuracoes",
                "/desligamentos",
            },
            "rh": {
                "/dashboard", "/importar", "/calendario", "/colaboradores",
                "/historico", "/relatorios",
                "/desligamentos",
            },
            "gestor": {
                "/dashboard", "/calendario", "/colaboradores", "/relatorios",
            },
            "consulta": {
                "/dashboard", "/calendario", "/colaboradores", "/relatorios",
            },
        }
        all_links = set().union(*expected_links.values())
        for profile, allowed in expected_links.items():
            html = self._sidebar_for(profile)
            for link in all_links:
                with self.subTest(profile=profile, link=link):
                    marker = f'href="{link}" class="nav-link'
                    self.assertEqual(marker in html, link in allowed)

            with self.subTest(profile=profile, link="Central de Inteligência"):
                self.assertEqual(
                    "Central de Inteligência" in html,
                    profile == "admin",
                )

    def test_intelligence_routes_are_admin_only(self):
        intelligence_paths = (
            "/", "/alertas", "/operacoes", "/dashboard/executivo",
            "/dashboard/rh", "/dashboard/ti",
        )
        clients = {
            profile: self._client_for(profile)
            for profile in ("admin", "rh", "gestor", "consulta")
        }

        with self._isolated_dashboard_routes():
            for path in intelligence_paths:
                with self.subTest(profile="admin", path=path):
                    self.assertEqual(clients["admin"].get(path).status_code, 200)

            for profile in ("rh", "gestor", "consulta"):
                for path in intelligence_paths:
                    with self.subTest(profile=profile, path=path):
                        self.assertEqual(clients[profile].get(path).status_code, 403)

    def test_operational_dashboard_remains_available_to_all_profiles(self):
        clients = {
            profile: self._client_for(profile)
            for profile in ("admin", "rh", "gestor", "consulta")
        }
        with self._isolated_dashboard_routes():
            for profile in ("admin", "rh", "gestor", "consulta"):
                with self.subTest(profile=profile):
                    self.assertEqual(
                        clients[profile].get("/dashboard").status_code, 200
                    )

    def test_dashboard_activities_card_uses_admin_only_permission(self):
        source = (BASE_DIR / "templates" / "dashboard.html").read_text(
            encoding="utf-8"
        )
        opening = (
            "{% if can_access('auditoria') %}"
            '<article class="dashboard-card activities-card">'
        )
        closing = "</article>{% endif %}"
        card_start = source.index(opening)
        card_end = source.index(closing, card_start)

        self.assertGreater(card_end, card_start)
        self.assertTrue(has_permission("admin", "auditoria"))
        for profile in ("rh", "gestor", "consulta"):
            with self.subTest(profile=profile):
                self.assertFalse(has_permission(profile, "auditoria"))

    def test_direct_url_access_is_denied_by_profile(self):
        forbidden = {
            "rh": ("/usuarios", "/configuracoes", "/auditoria"),
            "gestor": (
                "/importar", "/historico", "/usuarios", "/configuracoes",
                "/auditoria",
                "/desligamentos",
            ),
            "consulta": (
                "/importar", "/historico", "/usuarios", "/configuracoes",
                "/auditoria",
                "/desligamentos",
            ),
        }
        for profile, paths in forbidden.items():
            client = self._client_for(profile)
            for path in paths:
                with self.subTest(profile=profile, path=path):
                    self.assertEqual(client.get(path).status_code, 403)

        admin = self._client_for("admin")
        self.assertEqual(admin.get("/usuarios").status_code, 200)
        self.assertEqual(admin.get("/importar").status_code, 200)

    def test_rh_can_manage_vacation_data_but_not_users(self):
        client = self._client_for("rh")
        self.assertNotEqual(
            client.post("/colaboradores/inexistente/editar").status_code,
            403,
        )
        self.assertEqual(client.post("/usuarios/criar").status_code, 403)

    def test_manager_and_consultation_cannot_mutate_data(self):
        mutation_paths = (
            "/colaboradores/inexistente/editar",
            "/api/importacao/validar",
            "/configuracoes",
            "/usuarios/criar",
        )
        for profile in ("gestor", "consulta"):
            client = self._client_for(profile)
            for path in mutation_paths:
                with self.subTest(profile=profile, path=path):
                    self.assertEqual(client.post(path).status_code, 403)


if __name__ == "__main__":
    unittest.main()
