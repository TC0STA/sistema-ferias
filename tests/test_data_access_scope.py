import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from flask import Flask, session

from services.auth_service import load_current_user
from services.data_access_scope import (
    listar_importacoes_permitidas,
    obter_escopo_importacoes,
    usuario_e_admin,
    usuario_pode_acessar_importacao,
)
from services.import_log import ImportLogger
from services.user_service import UserService


class ImportDataAccessScopeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.import_database = self.root / "ferias.db"
        self.user_database = self.root / "usuarios.db"
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="scope-test-secret",
            DATABASE_PATH=str(self.import_database),
        )

        self.users = UserService(self.user_database)
        self.users.initialize()
        self.app.extensions["fokus_user_service"] = self.users
        self.admin = self.users.get_by_username("admin")
        self.nargela = self.users.create(
            nome="Nargela",
            usuario="nargela",
            email="nargela.scope@fokus.local",
            senha="senha-segura",
            perfil="rh",
        )
        self.mariney = self.users.create(
            nome="Mariney",
            usuario="mariney",
            email="mariney.scope@fokus.local",
            senha="senha-segura",
            perfil="rh",
        )
        self.sem_importacoes = self.users.create(
            nome="Sem Importações",
            usuario="sem.importacoes",
            email="sem.importacoes@fokus.local",
            senha="senha-segura",
            perfil="rh",
        )

        logger = ImportLogger(str(self.import_database))
        self.importacao_nargela = self._record_import(
            logger, "nargela.xlsx", self.nargela.nome, self.nargela.id
        )
        self.importacao_mariney = self._record_import(
            logger, "mariney.xlsx", self.mariney.nome, self.mariney.id
        )
        self.importacao_legada = self._record_import(
            logger, "legado.xlsx", "Usuário Antigo", None
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _record_import(self, logger, filename, username, user_id):
        version = logger.record_success(
            arquivo=filename,
            registros=1,
            erros=0,
            duracao_segundos=0.1,
            usuario=username,
            usuario_id=user_id,
            ip="127.0.0.1",
            comparacao={
                "novos": 1,
                "removidos": 0,
                "alterados": 0,
                "iguais": 0,
            },
            hash_arquivo=f"hash-{filename}",
        )
        conn = sqlite3.connect(self.import_database)
        importacao_id = conn.execute(
            "SELECT id FROM importacoes WHERE versao = ?", (version,)
        ).fetchone()[0]
        conn.close()
        return importacao_id

    @contextmanager
    def _as_user(self, user=None, path="/"):
        with self.app.test_request_context(path):
            if user is not None:
                session["user_id"] = user.id
            load_current_user()
            yield

    def test_nargela_ve_somente_a_propria_importacao(self):
        with self._as_user(self.nargela):
            importacoes = listar_importacoes_permitidas()

            self.assertEqual(
                [item["id"] for item in importacoes],
                [self.importacao_nargela],
            )
            self.assertTrue(
                usuario_pode_acessar_importacao(self.importacao_nargela)
            )
            self.assertFalse(
                usuario_pode_acessar_importacao(self.importacao_mariney)
            )
            self.assertFalse(
                usuario_pode_acessar_importacao(self.importacao_legada)
            )

    def test_mariney_ve_somente_a_propria_importacao(self):
        with self._as_user(self.mariney):
            importacoes = listar_importacoes_permitidas()

            self.assertEqual(
                [item["id"] for item in importacoes],
                [self.importacao_mariney],
            )
            self.assertFalse(
                usuario_pode_acessar_importacao(self.importacao_nargela)
            )
            self.assertTrue(
                usuario_pode_acessar_importacao(self.importacao_mariney)
            )
            self.assertFalse(
                usuario_pode_acessar_importacao(self.importacao_legada)
            )

    def test_admin_ve_importacoes_de_todos_e_o_legado(self):
        with self._as_user(self.admin):
            importacoes = listar_importacoes_permitidas()

            self.assertTrue(usuario_e_admin())
            self.assertEqual(
                [item["id"] for item in importacoes],
                [
                    self.importacao_nargela,
                    self.importacao_mariney,
                    self.importacao_legada,
                ],
            )
            self.assertTrue(
                usuario_pode_acessar_importacao(self.importacao_nargela)
            )
            self.assertTrue(
                usuario_pode_acessar_importacao(self.importacao_mariney)
            )
            self.assertTrue(
                usuario_pode_acessar_importacao(self.importacao_legada)
            )

    def test_usuario_sem_importacoes_recebe_lista_vazia(self):
        with self._as_user(self.sem_importacoes):
            self.assertEqual(listar_importacoes_permitidas(), [])

    def test_usuario_desativado_recebe_escopo_negado(self):
        self.users.set_active(self.nargela.id, False)

        with self._as_user(self.nargela):
            scope = obter_escopo_importacoes()

            self.assertFalse(scope.autenticado)
            self.assertEqual(listar_importacoes_permitidas(), [])
            self.assertFalse(
                usuario_pode_acessar_importacao(self.importacao_nargela)
            )

    def test_ids_inexistentes_recebem_acesso_negado(self):
        with self._as_user(self.nargela):
            self.assertFalse(usuario_pode_acessar_importacao(999999))
            self.assertFalse(usuario_pode_acessar_importacao("invalido"))

        with self._as_user(path="/?usuario_id=999999"):
            self.assertEqual(listar_importacoes_permitidas(), [])
            self.assertFalse(
                usuario_pode_acessar_importacao(self.importacao_nargela)
            )

        with self.app.test_request_context("/"):
            session["user_id"] = 999999
            load_current_user()
            self.assertFalse(obter_escopo_importacoes().autenticado)
            self.assertEqual(listar_importacoes_permitidas(), [])

    def test_parametro_de_cliente_nao_altera_o_escopo(self):
        path = f"/?usuario_id={self.mariney.id}"
        with self._as_user(self.nargela, path=path):
            importacoes = listar_importacoes_permitidas()

            self.assertEqual(
                [item["id"] for item in importacoes],
                [self.importacao_nargela],
            )

    def test_nargela_nao_acessa_importacao_da_mariney_pelo_id(self):
        with self._as_user(self.nargela):
            self.assertFalse(
                usuario_pode_acessar_importacao(self.importacao_mariney)
            )


if __name__ == "__main__":
    unittest.main()
