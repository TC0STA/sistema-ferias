import sqlite3
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path

from flask import Flask
from werkzeug.security import check_password_hash

from services.auth_service import authenticate
from services.user_service import UserService


class _StaticCursor:
    def __init__(self, row=None, rowcount: int = -1):
        self._row = row
        self.rowcount = rowcount

    def fetchone(self):
        return self._row


class _PostgreSQLTestConnection:
    """Executa o subconjunto SQL do serviço em SQLite para testar seu contrato."""

    def __init__(self, database_path: Path):
        self._connection = sqlite3.connect(database_path)
        self._connection.row_factory = sqlite3.Row

    def execute(self, statement: str, parameters=()):
        normalized = " ".join(statement.split()).upper()
        if "DROP TABLE" in normalized or "DELETE FROM USUARIOS" in normalized:
            raise AssertionError("A inicialização não pode apagar usuários.")
        if normalized.startswith("SELECT TO_REGCLASS"):
            return _StaticCursor({"exists": True})
        if normalized.startswith("CREATE TABLE IF NOT EXISTS USUARIOS"):
            return _StaticCursor()
        if normalized.startswith("CREATE UNIQUE INDEX IF NOT EXISTS"):
            return _StaticCursor()
        sqlite_parameters = tuple(
            value.isoformat() if isinstance(value, datetime) else value
            for value in parameters
        )
        return self._connection.execute(
            statement.replace("%s", "?"), sqlite_parameters
        )

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()


class _PostgreSQLUserService(UserService):
    def __init__(self, database_path: Path):
        self._test_database_path = database_path
        super().__init__("postgresql://teste@localhost/fokus")

    def _connect(self):
        return _PostgreSQLTestConnection(self._test_database_path)


class PostgreSQLUserPersistenceContractTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "postgresql-contract.db"
        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute("""
                CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    senha_hash TEXT NOT NULL,
                    perfil TEXT NOT NULL,
                    ativo INTEGER NOT NULL,
                    ultimo_login TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            connection.commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_lifecycle_and_login_persist_between_postgresql_connections(self):
        first_service = _PostgreSQLUserService(self.database_path)
        created = first_service.create(
            nome="Usuária PostgreSQL",
            usuario="postgres.persistente",
            email="postgres@fokus.local",
            senha="senha-inicial",
            perfil="consulta",
        )

        second_service = _PostgreSQLUserService(self.database_path)
        persisted = second_service.get_by_username("POSTGRES.PERSISTENTE")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.id, created.id)

        second_service.update(
            created.id,
            nome="Usuária PostgreSQL Editada",
            email="postgres.editada@fokus.local",
            perfil="gestor",
            ativo=False,
        )
        app = Flask("postgresql-persistence-contract")
        app.extensions["fokus_user_service"] = second_service
        with app.app_context():
            self.assertIsNone(authenticate("postgres.persistente", "senha-inicial"))

        second_service.set_active(created.id, True)
        second_service.reset_password(created.id, "senha-redefinida")
        third_service = _PostgreSQLUserService(self.database_path)
        app.extensions["fokus_user_service"] = third_service
        with app.app_context():
            logged_in = authenticate("postgres.persistente", "senha-redefinida")

        self.assertIsNotNone(logged_in)
        self.assertEqual(logged_in.nome, "Usuária PostgreSQL Editada")
        self.assertEqual(logged_in.perfil, "gestor")
        self.assertIsNotNone(logged_in.ultimo_login)
        self.assertTrue(check_password_hash(logged_in.senha_hash, "senha-redefinida"))
        self.assertEqual(third_service.count(), 1)


if __name__ == "__main__":
    unittest.main()
