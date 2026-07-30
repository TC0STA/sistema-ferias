import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.column_alias_store import ColumnAliasStore
from services.column_mapper import ColumnMapper


class ColumnMapperTestCase(unittest.TestCase):
    def test_normaliza_layouts_diferentes_para_o_mesmo_padrao(self):
        mapper = ColumnMapper()
        layouts = [
            (
                ["Usuário", "Data Início", "Data Fim"],
                {
                    "usuario": "Usuário",
                    "data_inicio": "Data Início",
                    "data_fim": "Data Fim",
                },
            ),
            (
                ["Colaborador", "Início", "Retorno"],
                {
                    "usuario": "Colaborador",
                    "data_inicio": "Início",
                    "data_fim": "Retorno",
                },
            ),
            (
                ["Funcionário", "Data Inicial", "Data Final"],
                {
                    "usuario": "Funcionário",
                    "data_inicio": "Data Inicial",
                    "data_fim": "Data Final",
                },
            ),
        ]

        for headers, expected in layouts:
            with self.subTest(headers=headers):
                result = mapper.discover(headers)
                self.assertTrue(result["completo"])
                self.assertEqual(result["colunas"], expected)

    def test_informa_campo_obrigatorio_nao_localizado(self):
        result = ColumnMapper().discover(["Usuário", "Data Início"])

        self.assertFalse(result["completo"])
        self.assertEqual(result["faltando"], [{
            "campo": "data_fim",
            "rotulo": "Data de Fim",
        }])

    def test_alias_persistido_e_consultado_sem_alterar_o_mapper(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "aliases.db"
            sqlite3.connect(database).close()
            store = ColumnAliasStore(str(database))
            mapper = ColumnMapper(alias_store=store)

            before = mapper.discover(["Associado", "Início", "Retorno"])
            store.save("Associado", "usuario")
            after = mapper.discover(["Associado", "Início", "Retorno"])

            self.assertFalse(before["completo"])
            self.assertTrue(after["completo"])
            self.assertEqual(after["colunas"]["usuario"], "Associado")


if __name__ == "__main__":
    unittest.main()
