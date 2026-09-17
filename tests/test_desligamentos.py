import re
import sqlite3
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
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret",
                               USER_DATABASE_PATH=str(self.database_path))
        register_blueprints(self.app)
        self.users: UserService = self.app.extensions["fokus_user_service"]
        self.terminations: TerminationService = self.app.extensions["fokus_termination_service"]
        self.rh = self.users.create(
            nome="Analista RH", usuario="rh.desligamentos",
            email="rh.desligamentos@fokus.local", senha="senha-segura", perfil="rh")
        self.manager = self.users.create(
            nome="Gestor", usuario="gestor.desligamentos",
            email="gestor.desligamentos@fokus.local", senha="senha-segura", perfil="gestor")

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
                "usuario": username, "senha": password, "csrf_token": token})
        self.assertEqual(response.status_code, 302)

    def _create_as_rh(self, *, nome="Colaborador Fantasma"):
        client = self.app.test_client()
        self._login(client, self.rh.usuario)
        token = self._token(client.get("/desligamentos"))
        with patch("routes.desligamentos.backend.registrar_auditoria") as audit:
            response = client.post("/desligamentos/criar", data={
                "csrf_token": token, "nome": nome, "perfil": "Vendedor",
                "departamento": "Vendas",
                "data_desligamento": date.today().isoformat(),
                "observacao": "Solicitação do RH"})
        self.assertEqual(response.status_code, 302)
        audit.assert_called_once()
        return client, self.terminations.list_all()[0]

    def _confirm_as_admin(self, record, *, follow_redirects=False):
        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        token = self._token(admin.get("/desligamentos"))
        with patch("routes.desligamentos.backend.registrar_auditoria") as audit:
            response = admin.post(f"/desligamentos/{record.id}/confirmar",
                                  data={"csrf_token": token},
                                  follow_redirects=follow_redirects)
        return response, audit

    def test_rh_creates_phantom_record_without_creating_user(self):
        initial_users = self.users.count()
        rh_client, record = self._create_as_rh()
        self.assertEqual(record.status, "PENDENTE")
        self.assertEqual(record.usuario_ad, "")
        self.assertEqual(record.email, "")
        self.assertEqual(record.filial, "")
        self.assertEqual(record.perfil, "Vendedor")
        self.assertEqual(record.departamento, "Vendas")
        self.assertEqual(record.data_desligamento, date.today())
        self.assertEqual(record.observacao, "Solicitação do RH")
        self.assertEqual(record.informado_por, self.rh.nome)
        self.assertEqual(self.users.count(), initial_users)
        page = rh_client.get("/desligamentos").get_data(as_text=True)
        self.assertIn("Colaborador Fantasma", page)
        self.assertNotIn("Selecionar usuário existente", page)

    def test_admin_confirms_without_modifying_matching_system_user(self):
        existing = self.users.create(
            nome="Conta Real", usuario="mesmo.login", email="mesmo@fokus.local",
            senha="senha-segura", perfil="consulta")
        initial_users = self.users.count()
        record = self.terminations.create(
            nome="Registro Informativo", usuario_ad=existing.usuario,
            email=existing.email, perfil="Vendedor", filial="Filial 11",
            departamento="Vendas", data_desligamento=date.today(),
            observacao="Solicitação do RH", informado_por=self.rh.nome)
        response, audit = self._confirm_as_admin(record)
        self.assertEqual(response.status_code, 302)
        audit.assert_called_once()
        processed = self.terminations.get_by_id(record.id)
        self.assertEqual(processed.status, "CONFIRMADO")
        self.assertIsNotNone(processed.data_confirmacao)
        self.assertEqual(processed.confirmado_por, "Administrador")
        self.assertTrue(self.users.get_by_id(existing.id).ativo)
        self.assertEqual(self.users.count(), initial_users)
        self.assertIn(record.id, [item.id for item in self.terminations.list_all()])

    def test_confirmation_is_rejected_after_first_processing(self):
        _, record = self._create_as_rh()
        self._confirm_as_admin(record)
        response, audit = self._confirm_as_admin(record, follow_redirects=True)
        self.assertIn("já foi processada", response.get_data(as_text=True))
        audit.assert_not_called()
        self.assertEqual(self.terminations.get_by_id(record.id).status, "CONFIRMADO")

    def test_rh_cannot_confirm_and_unpermitted_profile_cannot_access(self):
        rh_client, record = self._create_as_rh()
        token = self._token(rh_client.get("/desligamentos"))
        response = rh_client.post(f"/desligamentos/{record.id}/confirmar",
                                  data={"csrf_token": token})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.terminations.get_by_id(record.id).status, "PENDENTE")
        manager = self.app.test_client()
        self._login(manager, self.manager.usuario)
        self.assertEqual(manager.get("/desligamentos").status_code, 403)

    def test_authorized_users_see_shared_termination_register(self):
        rh_client, _ = self._create_as_rh()
        self.terminations.create(
            nome="Outra Pessoa", usuario_ad="outra.pessoa", email="outra@fokus.local",
            perfil="Vendedor", filial="Filial Norte", departamento="Comercial",
            data_desligamento=date.today(), observacao="Administrativa",
            informado_por="Administrador")
        page = rh_client.get("/desligamentos").get_data(as_text=True)
        self.assertIn("Colaborador Fantasma", page)
        self.assertIn("Outra Pessoa", page)

    def test_dashboard_counts_only_pending_records(self):
        rh_client, record = self._create_as_rh()
        self.assertNotIn("desligamento(s) pendente(s)",
                         rh_client.get("/dashboard").get_data(as_text=True))
        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        self.assertIn("1 desligamento(s) pendente(s)",
                      admin.get("/dashboard").get_data(as_text=True))
        self._confirm_as_admin(record)
        self.assertEqual(self.terminations.count_pending(), 0)

    def test_cancelled_request_remains_in_history(self):
        _, record = self._create_as_rh()
        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        token = self._token(admin.get("/desligamentos"))
        admin.post(f"/desligamentos/{record.id}/cancelar", data={"csrf_token": token})
        cancelled = self.terminations.get_by_id(record.id)
        self.assertEqual(cancelled.status, "CANCELADO")
        self.assertIn(cancelled.id, [item.id for item in self.terminations.list_all()])

    def test_admin_edits_pending_informational_fields(self):
        _, record = self._create_as_rh()
        admin = self.app.test_client()
        self._login(admin, "admin", "admin123")
        token = self._token(admin.get("/desligamentos"))
        response = admin.post(f"/desligamentos/{record.id}/editar", data={
            "csrf_token": token, "nome": "Nome Corrigido",
            "usuario_ad": "login.corrigido", "email": "corrigido@fokus.local",
            "perfil": "Analista", "filial": "Filial Sul", "departamento": "Financeiro",
            "data_desligamento": date.today().isoformat(), "observacao": "Corrigido"})
        self.assertEqual(response.status_code, 302)
        edited = self.terminations.get_by_id(record.id)
        self.assertEqual(edited.usuario_ad, "login.corrigido")
        self.assertEqual(edited.status, "PENDENTE")

    def test_invalid_identity_is_rejected(self):
        client = self.app.test_client()
        self._login(client, self.rh.usuario)
        token = self._token(client.get("/desligamentos"))
        response = client.post("/desligamentos/criar", data={
            "csrf_token": token, "nome": "",
            "data_desligamento": "data-invalida"}, follow_redirects=True)
        self.assertIn("Nome do colaborador é obrigatório", response.get_data(as_text=True))
        self.assertEqual(self.terminations.count_pending(), 0)

    def test_create_modal_contains_only_requested_fields(self):
        client = self.app.test_client()
        self._login(client, self.rh.usuario)
        page = client.get("/desligamentos").get_data(as_text=True)
        create_modal = page.split('id="createTermination"', 1)[1].split(
            'id="editTermination"', 1
        )[0]
        for field in ("nome", "perfil", "departamento", "data_desligamento", "observacao"):
            self.assertIn(f'name="{field}"', create_modal)
        for field in ("usuario_ad", "email", "filial"):
            self.assertNotIn(f'name="{field}"', create_modal)
        self.assertIn("Cancelar", create_modal)
        self.assertIn("Salvar solicitação", create_modal)

    def test_records_persist_between_service_instances(self):
        _, created = self._create_as_rh()
        reopened = TerminationService(self.database_path).get_by_id(created.id)
        self.assertEqual(reopened.usuario_ad, "")
        self.assertEqual(reopened.status, "PENDENTE")


class TerminationMigrationTests(unittest.TestCase):
    def test_legacy_schema_is_migrated_without_user_references_or_data_loss(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "legacy.db"
            connection = sqlite3.connect(database)
            connection.execute("""
                CREATE TABLE desligamentos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
                    nome TEXT NOT NULL, usuario TEXT NOT NULL, email TEXT NOT NULL,
                    perfil TEXT NOT NULL, filial TEXT NOT NULL, departamento TEXT NOT NULL,
                    data_desligamento TEXT NOT NULL, observacao TEXT NOT NULL,
                    status TEXT NOT NULL, solicitado_por_id INTEGER NOT NULL,
                    solicitado_por TEXT NOT NULL, solicitado_em TEXT NOT NULL,
                    desativado_por TEXT, desativado_em TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL)
            """)
            values = (99, "Legado", "legado.ad", "legado@fokus.local", "Vendedor",
                      "Matriz", "Vendas", "2026-08-20", "Preservar", "Desativado",
                      7, "RH Legado", "2026-08-10T10:00:00", "TI Legado",
                      "2026-08-20T18:00:00", "2026-08-10T10:00:00",
                      "2026-08-20T18:00:00")
            connection.execute(
                "INSERT INTO desligamentos (user_id,nome,usuario,email,perfil,filial,"
                "departamento,data_desligamento,observacao,status,solicitado_por_id,"
                "solicitado_por,solicitado_em,desativado_por,desativado_em,created_at,"
                "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
            connection.commit()
            connection.close()

            service = TerminationService(database)
            service.ensure_schema()
            migrated = service.list_all()[0]
            self.assertEqual(migrated.nome, "Legado")
            self.assertEqual(migrated.usuario_ad, "legado.ad")
            self.assertEqual(migrated.status, "CONFIRMADO")
            self.assertEqual(migrated.informado_por, "RH Legado")
            self.assertEqual(migrated.confirmado_por, "TI Legado")

            connection = sqlite3.connect(database)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(desligamentos)")}
            foreign_keys = list(connection.execute("PRAGMA foreign_key_list(desligamentos)"))
            connection.close()
            self.assertNotIn("user_id", columns)
            self.assertNotIn("solicitado_por_id", columns)
            self.assertEqual(foreign_keys, [])


if __name__ == "__main__":
    unittest.main()
