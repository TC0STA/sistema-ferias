import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import app as sistema
import backend
from services.collaborator_profile_service import CollaboratorProfileService
from services.import_log import ImportLogger
from services.user_service import UserService


class CollaboratorProfileMigrationTests(unittest.TestCase):
    def test_migration_preserves_legacy_rows_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database = root / "ferias.db"
            backups = root / "backups"
            conn = sqlite3.connect(database)
            conn.execute("""
                CREATE TABLE colaborador_perfis (
                    nome TEXT PRIMARY KEY,
                    departamento TEXT,
                    cargo TEXT,
                    matricula TEXT,
                    filial TEXT,
                    atualizado_em TEXT
                )
            """)
            conn.executemany("""
                INSERT INTO colaborador_perfis (
                    nome, departamento, cargo, matricula, filial, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, [
                ("Ana", "RH", "Analista", "100", "Norte", "2026-01-01"),
                ("Bruno", "TI", "Técnico", "200", "Sul", "2026-01-02"),
            ])
            conn.commit()
            conn.close()

            service = CollaboratorProfileService(str(database), str(backups))
            service.ensure_schema()
            service.ensure_schema()

            conn = sqlite3.connect(database)
            columns = {
                row[1] for row in conn.execute(
                    "PRAGMA table_info(colaborador_perfis)"
                ).fetchall()
            }
            rows = conn.execute("""
                SELECT usuario_id, nome, departamento, cargo, matricula,
                       filial, atualizado_em
                FROM colaborador_perfis ORDER BY nome
            """).fetchall()
            indexes = {
                row[1] for row in conn.execute(
                    "PRAGMA index_list(colaborador_perfis)"
                ).fetchall()
            }
            conn.close()

            self.assertTrue({
                "id", "usuario_id", "colaborador_chave", "nome"
            }.issubset(columns))
            self.assertEqual(rows, [
                (None, "Ana", "RH", "Analista", "100", "Norte", "2026-01-01"),
                (None, "Bruno", "TI", "Técnico", "200", "Sul", "2026-01-02"),
            ])
            self.assertIn("colaborador_perfis_escopo_chave_uidx", indexes)
            self.assertEqual(
                len(list(backups.rglob("ferias_antes_colaborador_perfis_*.db"))),
                1,
            )


class CollaboratorIsolationIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database = self.root / "ferias.db"
        self.uploads = self.root / "uploads"
        self.backups = self.root / "backups"
        self.uploads.mkdir()
        self.originals = {
            "database": backend.DATABASE_PATH,
            "uploads": backend.UPLOAD_FOLDER,
            "backups": backend.BACKUPS_DIR,
            "pasta_padrao": backend.CONFIGURACOES_PADRAO["pasta_padrao"],
            "app_database": sistema.app.config.get("DATABASE_PATH"),
            "user_service": sistema.app.extensions["fokus_user_service"],
        }
        backend.DATABASE_PATH = str(self.database)
        backend.UPLOAD_FOLDER = str(self.uploads)
        backend.BACKUPS_DIR = str(self.backups)
        backend.CONFIGURACOES_PADRAO["pasta_padrao"] = str(self.uploads)
        sistema.app.config.update(
            TESTING=True,
            DATABASE_PATH=str(self.database),
        )
        backend.inicializar_tabelas_sistema()

        self.users = UserService(self.root / "usuarios.db")
        self.users.initialize()
        self.admin = self.users.get_by_username("admin")
        self.nargela = self.users.create(
            nome="Nargela", usuario="nargela.colaboradores",
            email="nargela.colaboradores@fokus.local",
            senha="senha-segura", perfil="rh",
        )
        self.mariney = self.users.create(
            nome="Mariney", usuario="mariney.colaboradores",
            email="mariney.colaboradores@fokus.local",
            senha="senha-segura", perfil="rh",
        )
        self.sem_importacoes = self.users.create(
            nome="Sem Importações", usuario="sem.colaboradores",
            email="sem.colaboradores@fokus.local",
            senha="senha-segura", perfil="rh",
        )
        sistema.app.extensions["fokus_user_service"] = self.users

        self._create_import(
            "nargela.xlsx", "João da Silva", "100", "Setor Nargela",
            self.nargela.id, self.nargela.nome,
        )
        self._create_import(
            "mariney.xlsx", "João da Silva", "200", "Setor Mariney",
            self.mariney.id, self.mariney.nome,
        )
        self._create_import(
            "legado.xlsx", "Colaborador Legado", "300", "Setor Legado",
            None, "Usuário Antigo",
        )

    def tearDown(self):
        backend.DATABASE_PATH = self.originals["database"]
        backend.UPLOAD_FOLDER = self.originals["uploads"]
        backend.BACKUPS_DIR = self.originals["backups"]
        backend.CONFIGURACOES_PADRAO["pasta_padrao"] = self.originals[
            "pasta_padrao"
        ]
        if self.originals["app_database"] is None:
            sistema.app.config.pop("DATABASE_PATH", None)
        else:
            sistema.app.config["DATABASE_PATH"] = self.originals["app_database"]
        sistema.app.extensions["fokus_user_service"] = self.originals[
            "user_service"
        ]
        self.temp_dir.cleanup()

    def _create_import(
        self, filename, name, registration, department, user_id, username
    ):
        path = self.uploads / filename
        pd.DataFrame([{
            "Nome": name,
            "Inicio": "01/10/2026",
            "Fim": "10/10/2026",
            "Matrícula": registration,
            "Departamento": department,
            "Cargo": "Analista",
            "Filial": "Filial Teste",
        }]).to_excel(path, index=False)
        ImportLogger(str(self.database)).record_success(
            arquivo=filename,
            arquivo_armazenado=filename,
            registros=1,
            erros=0,
            duracao_segundos=0.1,
            usuario=username,
            usuario_id=user_id,
            ip="127.0.0.1",
            comparacao={
                "novos": 1, "removidos": 0, "alterados": 0, "iguais": 0
            },
            hash_arquivo=f"hash-{filename}",
        )

    def _client_for(self, user):
        client = sistema.app.test_client()
        with client.session_transaction() as browser_session:
            browser_session["user_id"] = user.id
        return client

    def _identifiers(self, response):
        html = response.get_data(as_text=True)
        return list(dict.fromkeys(re.findall(
            r'href="/colaboradores/([^"?]+)', html
        )))

    def test_each_user_lists_only_their_own_collaborators(self):
        nargela_page = self._client_for(self.nargela).get("/colaboradores")
        mariney_page = self._client_for(self.mariney).get("/colaboradores")
        empty_page = self._client_for(self.sem_importacoes).get("/colaboradores")

        self.assertIn("Setor Nargela", nargela_page.get_data(as_text=True))
        self.assertNotIn("Setor Mariney", nargela_page.get_data(as_text=True))
        self.assertNotIn("Setor Legado", nargela_page.get_data(as_text=True))
        self.assertIn("Setor Mariney", mariney_page.get_data(as_text=True))
        self.assertNotIn("Setor Nargela", mariney_page.get_data(as_text=True))
        self.assertNotIn("Setor Legado", mariney_page.get_data(as_text=True))
        self.assertIn("Nenhum colaborador encontrado", empty_page.get_data(as_text=True))

    def test_admin_sees_owners_legacy_and_distinct_homonyms(self):
        client = self._client_for(self.admin)
        response = client.get("/colaboradores")
        html = response.get_data(as_text=True)
        identifiers = self._identifiers(response)

        self.assertIn("Setor Nargela", html)
        self.assertIn("Setor Mariney", html)
        self.assertIn("Setor Legado", html)
        self.assertEqual(len(identifiers), 3)
        details = [
            client.get(f"/colaboradores/{identifier}").get_data(as_text=True)
            for identifier in identifiers
        ]
        self.assertTrue(any("Setor Nargela" in page for page in details))
        self.assertTrue(any("Setor Mariney" in page for page in details))
        self.assertTrue(any("Setor Legado" in page for page in details))
        self.assertEqual(sum("João da Silva" in page for page in details), 2)

    def test_direct_detail_and_edit_of_another_owner_return_404(self):
        admin = self._client_for(self.admin)
        identifiers = self._identifiers(admin.get("/colaboradores"))
        mariney_identifier = next(
            identifier for identifier in identifiers
            if "Setor Mariney" in admin.get(
                f"/colaboradores/{identifier}"
            ).get_data(as_text=True)
        )
        nargela = self._client_for(self.nargela)

        self.assertEqual(
            nargela.get(f"/colaboradores/{mariney_identifier}").status_code,
            404,
        )
        self.assertEqual(nargela.post(
            f"/colaboradores/{mariney_identifier}/editar",
            data={
                "departamento": "Invasão", "cargo": "X",
                "matricula": "999", "filial": "Outra",
                "usuario_id": self.mariney.id,
            },
        ).status_code, 404)

    def test_owner_edit_is_scoped_and_client_owner_is_ignored(self):
        nargela = self._client_for(self.nargela)
        identifier = self._identifiers(nargela.get("/colaboradores"))[0]
        response = nargela.post(
            f"/colaboradores/{identifier}/editar?usuario_id={self.mariney.id}",
            data={
                "departamento": "Nargela Editado",
                "cargo": "Coordenadora",
                "matricula": "100",
                "filial": "Filial Nargela",
                "usuario_id": self.mariney.id,
            },
        )

        self.assertEqual(response.status_code, 302)
        conn = sqlite3.connect(self.database)
        rows = conn.execute("""
            SELECT usuario_id, departamento FROM colaborador_perfis
            ORDER BY id
        """).fetchall()
        conn.close()
        self.assertEqual(rows, [(self.nargela.id, "Nargela Editado")])
        self.assertIn(
            "Nargela Editado",
            nargela.get("/colaboradores").get_data(as_text=True),
        )

    def test_admin_can_edit_each_homonym_without_mixing_profiles(self):
        admin = self._client_for(self.admin)
        identifiers = self._identifiers(admin.get("/colaboradores"))
        owner_identifiers = {}
        for identifier in identifiers:
            detail = admin.get(
                f"/colaboradores/{identifier}"
            ).get_data(as_text=True)
            if "Setor Nargela" in detail:
                owner_identifiers[self.nargela.id] = identifier
            elif "Setor Mariney" in detail:
                owner_identifiers[self.mariney.id] = identifier

        for user_id, department in (
            (self.nargela.id, "Admin Nargela"),
            (self.mariney.id, "Admin Mariney"),
        ):
            response = admin.post(
                f"/colaboradores/{owner_identifiers[user_id]}/editar",
                data={
                    "departamento": department, "cargo": "Admin Editou",
                    "matricula": "100" if user_id == self.nargela.id else "200",
                    "filial": "Filial Admin",
                },
            )
            self.assertEqual(response.status_code, 302)

        conn = sqlite3.connect(self.database)
        rows = conn.execute("""
            SELECT usuario_id, departamento FROM colaborador_perfis
            ORDER BY usuario_id
        """).fetchall()
        conn.close()
        self.assertEqual(rows, [
            (self.nargela.id, "Admin Nargela"),
            (self.mariney.id, "Admin Mariney"),
        ])

    def test_invalid_or_tampered_identifier_returns_404(self):
        client = self._client_for(self.nargela)
        identifier = self._identifiers(client.get("/colaboradores"))[0]

        self.assertEqual(
            client.get(f"/colaboradores/{identifier}alterado").status_code,
            404,
        )
        self.assertEqual(
            client.get("/colaboradores/colaborador-inexistente").status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
