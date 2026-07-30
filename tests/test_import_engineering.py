import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import app as sistema
from services.audit_service import AuditService
from services.backup import BackupService
from services.column_mapper import ColumnMapper, assinatura_colunas
from services.column_mapping_store import ColumnMappingStore
from services.compare_service import CompareService
from services.dashboard_updater import DashboardUpdater
from services.file_reader import FileReader
from services.events import EventBus
from services.import_compare import ImportComparator
from services.import_engine import ImportEngine
from services.import_log import ImportLogger
from services.import_plugin import (
    ImportPlugin,
    ImportPluginContext,
    PluginExecutionError,
)
from services.import_preview import ImportPreview
from services.import_profile import ImportProfileStore
from services.import_service import ImportService
from services.plugin_manager import ImportPluginManager
from services.import_validator import ImportValidator


class ImportEngineeringTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database = self.root / "fokus.db"
        conn = sqlite3.connect(self.database)
        conn.execute(
            "CREATE TABLE controle (id INTEGER PRIMARY KEY, valor TEXT)"
        )
        conn.execute("INSERT INTO controle (valor) VALUES ('original')")
        conn.commit()
        conn.close()

    def tearDown(self):
        self.temp_dir.cleanup()

    def criar_planilha(self, nome, registros):
        caminho = self.root / nome
        pd.DataFrame(registros).to_excel(caminho, index=False)
        return caminho

    def validar_planilha(self, caminho, validator=None):
        validator = validator or ImportValidator()
        file_data = FileReader().read(str(caminho))
        mapping = ColumnMapper().discover(
            file_data.columns,
            obrigatorias=validator.colunas_obrigatorias
        )
        return validator.validate_dataframe(
            file_data.dataframe,
            filename=file_data.filename,
            header_row=file_data.header_row,
            mapping=mapping,
            file_info={
                "ok": True,
                "extensao": file_data.extension,
                "tamanho_bytes": file_data.size_bytes
            }
        ).to_dict()

    def test_validator_retorna_resultado_completo_linha_por_linha(self):
        caminho = self.criar_planilha(
            "ferias.xlsx",
            [
                {
                    "Nome": "Ana",
                    "Data Inicio": "01/08/2026",
                    "Data Fim": "10/08/2026",
                    "Departamento": "RH",
                    "Matrícula": "100"
                },
                {
                    "Nome": "",
                    "Data Inicio": "data inválida",
                    "Data Fim": "12/08/2026",
                    "Departamento": "",
                    "Matrícula": ""
                }
            ]
        )

        resultado = self.validar_planilha(caminho)

        self.assertEqual(resultado["arquivo"], "ferias.xlsx")
        self.assertEqual(resultado["total_registros"], 2)
        self.assertEqual(resultado["validos"], 1)
        self.assertEqual(resultado["invalidos"], 1)
        self.assertFalse(resultado["pronta"])
        self.assertEqual(resultado["status"], "ERRO")
        self.assertEqual(resultado["total"], 2)
        self.assertTrue(resultado["validacao_arquivo"]["ok"])
        self.assertEqual(
            [linha["status"] for linha in resultado["linhas"]],
            ["OK", "ERRO"]
        )
        self.assertEqual(
            {erro["campo"] for erro in resultado["erros"]},
            {"Nome", "Data Início", "Departamento", "Matrícula"}
        )

    def test_file_reader_apenas_devolve_dataframe_e_metadados(self):
        caminho = self.criar_planilha(
            "leitura.xlsx",
            [{
                "Colaborador": "Ana",
                "Início": "01/08/2026",
                "Retorno": "10/08/2026"
            }]
        )

        dados = FileReader().read(str(caminho))

        self.assertEqual(dados.filename, "leitura.xlsx")
        self.assertEqual(dados.header_row, 0)
        self.assertEqual(
            dados.columns,
            ["Colaborador", "Início", "Retorno"]
        )
        self.assertEqual(dados.dataframe.iloc[0]["Colaborador"], "Ana")

    def test_file_reader_merge_duas_linhas_de_cabecalho(self):
        caminho = self.root / "cabecalho_duas_linhas.xlsx"
        with pd.ExcelWriter(caminho, engine="openpyxl") as writer:
            df = pd.DataFrame([
                ["Ana", "01/08/2026", "10/08/2026"]
            ])
            df.to_excel(writer, index=False, header=False, startrow=2)
            workbook = writer.book
            worksheet = writer.sheets["Sheet1"]
            worksheet["A1"] = "Nome"
            worksheet["B1"] = "Data"
            worksheet["C1"] = "Data"
            worksheet["A2"] = ""
            worksheet["B2"] = "Início"
            worksheet["C2"] = "Fim"

        dados = FileReader().read(str(caminho))

        self.assertEqual(dados.header_row, 0)
        self.assertEqual(
            dados.columns,
            ["Nome", "Data Início", "Data Fim"]
        )
        self.assertEqual(dados.dataframe.iloc[0]["Nome"], "Ana")

    def test_validator_recebe_dataframe_sem_acessar_arquivo(self):
        dataframe = pd.DataFrame([{
            "Colaborador": "Ana",
            "Início": "01/08/2026",
            "Retorno": "10/08/2026"
        }])
        mapping = ColumnMapper().discover(dataframe.columns)

        resultado = ImportValidator().validate_dataframe(
            dataframe,
            filename="memoria.xlsx",
            header_row=0,
            mapping=mapping
        ).to_dict()

        self.assertTrue(resultado["pronta"])
        self.assertEqual(resultado["total"], 1)

    def test_preview_calcula_estatisticas_sem_dependencias_externas(self):
        dataframe = pd.DataFrame([
            {
                "Colaborador": "Ana",
                "Início": "01/08/2026",
                "Retorno": "10/08/2026",
                "Setor": "RH"
            },
            {
                "Colaborador": "Bruno",
                "Início": "05/08/2026",
                "Retorno": "18/09/2026",
                "Setor": "Operações"
            },
            {
                "Colaborador": "Ana",
                "Início": "20/08/2026",
                "Retorno": "30/08/2026",
                "Setor": "RH"
            }
        ])
        mapping = ColumnMapper().discover(dataframe.columns)
        validation = ImportValidator().validate_dataframe(
            dataframe,
            filename="Ferias_Agosto.xlsx",
            header_row=0,
            mapping=mapping
        ).to_dict()

        resumo = ImportPreview().build(
            dataframe,
            mapping=mapping,
            validation=validation
        )

        self.assertEqual(resumo["registros_encontrados"], 3)
        self.assertEqual(resumo["usuarios_unicos"], 2)
        self.assertEqual(resumo["departamentos"], 2)
        self.assertEqual(resumo["periodo"], {
            "inicio": "01/08/2026",
            "fim": "18/09/2026"
        })
        self.assertEqual(resumo["datas_invalidas"], 0)
        self.assertEqual(
            [item["identificada"] for item in resumo["colunas_identificadas"]],
            [True, True, True]
        )

    def test_validator_identifica_linha_vazia_no_dataframe(self):
        dataframe = pd.DataFrame([
            {"Nome": "Ana", "Início": "01/08/2026", "Fim": "10/08/2026"},
            {"Nome": None, "Início": None, "Fim": None},
            {"Nome": "Bruno", "Início": "02/08/2026", "Fim": "11/08/2026"}
        ])
        mapping = ColumnMapper().discover(dataframe.columns)

        resultado = ImportValidator().validate_dataframe(
            dataframe,
            filename="linhas.xlsx",
            header_row=0,
            mapping=mapping
        ).to_dict()

        self.assertFalse(resultado["pronta"])
        self.assertEqual(resultado["invalidos"], 1)
        self.assertEqual(
            resultado["campos_obrigatorios"]["linhas_vazias"],
            1
        )
        self.assertEqual(resultado["erros"][0]["campo"], "Linha")

    def test_validator_aceita_colunas_opcionais_ausentes(self):
        caminho = self.criar_planilha(
            "ferias_minima.xlsx",
            [{
                "Nome": "Ana",
                "Inicio": "01/08/2026",
                "Fim": "10/08/2026"
            }]
        )

        resultado = self.validar_planilha(caminho)

        self.assertTrue(resultado["pronta"])
        self.assertEqual(resultado["validos"], 1)
        self.assertFalse(
            resultado["campos_obrigatorios"]["matricula_presente"]
        )
        self.assertFalse(
            resultado["campos_obrigatorios"]["departamento_presente"]
        )

    def test_validator_rejeita_extensao_vazia_e_arquivo_corrompido(self):
        csv = self.root / "ferias.csv"
        csv.write_text("Nome,Inicio,Fim", encoding="utf-8")
        vazio = self.root / "vazio.xlsx"
        vazio.touch()
        corrompido = self.root / "corrompido.xlsx"
        corrompido.write_bytes(b"conteudo que nao e um arquivo Excel")
        sem_registros = self.criar_planilha(
            "sem_registros.xlsx",
            pd.DataFrame(columns=["Nome", "Inicio", "Fim"])
        )

        service = ImportService(
            database_path=str(self.database),
            backups_root=str(self.root / "backups")
        )
        resultados = [
            service.analyze(str(caminho))
            for caminho in (csv, vazio, corrompido, sem_registros)
        ]

        self.assertTrue(all(item["status"] == "ERRO" for item in resultados))
        self.assertTrue(
            all(not item["validacao_arquivo"]["ok"] for item in resultados)
        )
        self.assertIn("Formato inválido", resultados[0]["erros"][0]["erro"])
        self.assertIn("vazio", resultados[1]["erros"][0]["erro"])
        self.assertIn("corrompido", resultados[2]["erros"][0]["erro"])
        self.assertIn("não contém registros", resultados[3]["erros"][0]["erro"])

    def test_validator_detecta_matricula_duplicada(self):
        caminho = self.criar_planilha(
            "matriculas.xlsx",
            [
                {
                    "Nome": "Ana",
                    "Inicio": "01/08/2026",
                    "Fim": "10/08/2026",
                    "Matrícula": "100"
                },
                {
                    "Nome": "Bruno",
                    "Inicio": "02/08/2026",
                    "Fim": "11/08/2026",
                    "Matrícula": "100"
                }
            ]
        )

        resultado = self.validar_planilha(caminho)

        self.assertFalse(resultado["pronta"])
        self.assertEqual(resultado["invalidos"], 1)
        self.assertEqual(resultado["duplicidade"]["matriculas"], 1)
        self.assertEqual(resultado["erros"][0]["campo"], "Matrícula")

    def test_validator_permite_configurar_matricula_como_obrigatoria(self):
        caminho = self.criar_planilha(
            "sem_matricula.xlsx",
            [{
                "Nome": "Ana",
                "Inicio": "01/08/2026",
                "Fim": "10/08/2026"
            }]
        )
        validator = ImportValidator(
            colunas_obrigatorias=("nome", "inicio", "fim", "matricula")
        )

        resultado = self.validar_planilha(caminho, validator)

        self.assertFalse(resultado["pronta"])
        self.assertIn("Matrícula", resultado["estrutura"]["faltando"])

    def test_comparator_identifica_novos_removidos_alterados_e_iguais(self):
        anterior = self.criar_planilha(
            "anterior.xlsx",
            [
                {
                    "Nome": "Ana",
                    "Inicio": "01/08/2026",
                    "Fim": "10/08/2026"
                },
                {
                    "Nome": "Bruno",
                    "Inicio": "02/08/2026",
                    "Fim": "12/08/2026"
                },
                {
                    "Nome": "Carlos",
                    "Inicio": "03/08/2026",
                    "Fim": "13/08/2026"
                }
            ]
        )
        nova = self.criar_planilha(
            "nova.xlsx",
            [
                {
                    "Nome": "Ana",
                    "Inicio": "01/08/2026",
                    "Fim": "10/08/2026"
                },
                {
                    "Nome": "Bruno",
                    "Inicio": "20/08/2026",
                    "Fim": "30/08/2026"
                },
                {
                    "Nome": "Daniela",
                    "Inicio": "04/08/2026",
                    "Fim": "14/08/2026"
                }
            ]
        )

        resultado = ImportComparator().compare(str(anterior), str(nova))

        self.assertEqual(resultado, {
            "novos": 1,
            "removidos": 1,
            "alterados": 1,
            "iguais": 1
        })

    def test_compare_service_opera_somente_com_dataframes(self):
        anterior = pd.DataFrame([
            {"Pessoa": "Ana", "Saída": "01/08/2026", "Volta": "10/08/2026"}
        ])
        atual = pd.DataFrame([
            {"Nome": "Ana", "Início": "02/08/2026", "Fim": "11/08/2026"},
            {"Nome": "Bruno", "Início": "03/08/2026", "Fim": "12/08/2026"}
        ])

        resultado = CompareService().compare(
            anterior,
            atual,
            previous_mapping={
                "nome": "Pessoa",
                "inicio": "Saída",
                "fim": "Volta"
            },
            current_mapping={
                "nome": "Nome",
                "inicio": "Início",
                "fim": "Fim"
            }
        )

        self.assertEqual(resultado, {
            "novos": 1,
            "removidos": 0,
            "alterados": 1,
            "iguais": 0
        })

    def test_column_mapper_reconhece_sinonimos_do_rh(self):
        resultado = ColumnMapper().discover(
            ["Colaborador", "Início das Férias", "Retorno"],
            obrigatorias=("nome", "inicio", "fim")
        )

        self.assertTrue(resultado["completo"])
        self.assertFalse(resultado["requer_confirmacao"])
        self.assertEqual(resultado["colunas"], {
            "nome": "Colaborador",
            "inicio": "Início das Férias",
            "fim": "Retorno"
        })

    def test_column_mapper_sinaliza_ambiguidade_com_opcoes(self):
        resultado = ColumnMapper().discover(
            ["Nome", "Colaborador", "Início", "Fim"],
            obrigatorias=("nome", "inicio", "fim")
        )

        self.assertFalse(resultado["completo"])
        self.assertTrue(resultado["requer_confirmacao"])
        self.assertEqual(resultado["ambiguidades"][0]["rotulo"], "Usuário")
        self.assertEqual(
            resultado["ambiguidades"][0]["opcoes"],
            ["Nome", "Colaborador"]
        )
        self.assertIn(
            "Escolha uma",
            resultado["ambiguidades"][0]["mensagem"]
        )

    def test_mapping_store_reutiliza_modelo_confirmado(self):
        store = ColumnMappingStore(str(self.database))
        colunas = ["Nome Completo", "Saída", "Retorno"]
        mapeamento = {
            "nome": "Nome Completo",
            "inicio": "Saída",
            "fim": "Retorno"
        }

        store.save(colunas, mapeamento)

        self.assertEqual(store.load(colunas), mapeamento)
        self.assertIsNone(store.load(["Outra", "Estrutura"]))

    def test_perfis_distintos_por_layout_e_origem(self):
        store = ImportProfileStore(str(self.database))
        goias = store.save(
            ["Colaborador", "Início", "Retorno"],
            {
                "nome": "Colaborador",
                "inicio": "Início",
                "fim": "Retorno"
            },
            nome="RH Goiás",
            arquivo_referencia="Ferias_RH_GO.xlsx",
            origem="Goiás",
            confirmado=True
        )
        sao_paulo = store.save(
            ["Funcionário", "Data Inicial", "Data Final"],
            {
                "nome": "Funcionário",
                "inicio": "Data Inicial",
                "fim": "Data Final"
            },
            nome="RH São Paulo",
            arquivo_referencia="Ferias_RH_SP.xlsx",
            origem="São Paulo",
            confirmado=True
        )

        perfis = store.list()

        self.assertNotEqual(goias["assinatura"], sao_paulo["assinatura"])
        self.assertEqual(
            {perfil["nome"] for perfil in perfis},
            {"RH Goiás", "RH São Paulo"}
        )
        self.assertEqual(goias["origem"], "Goiás")
        self.assertEqual(sao_paulo["origem"], "São Paulo")

    def test_perfis_migram_mapeamentos_existentes(self):
        colunas = ["Colaborador", "Início", "Retorno"]
        mapeamento = {
            "nome": "Colaborador",
            "inicio": "Início",
            "fim": "Retorno"
        }
        assinatura = assinatura_colunas(colunas)
        conn = sqlite3.connect(self.database)
        conn.execute("""
            CREATE TABLE mapeamentos_colunas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                assinatura TEXT NOT NULL UNIQUE,
                colunas_json TEXT NOT NULL,
                mapeamento_json TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            )
        """)
        conn.execute(
            """
            INSERT INTO mapeamentos_colunas (
                assinatura, colunas_json, mapeamento_json,
                criado_em, atualizado_em
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                assinatura,
                json.dumps(colunas, ensure_ascii=False),
                json.dumps(mapeamento, ensure_ascii=False),
                "2026-07-29T08:00:00",
                "2026-07-29T08:00:00"
            )
        )
        conn.commit()
        conn.close()

        perfis = ImportProfileStore(str(self.database)).list()

        self.assertEqual(len(perfis), 1)
        self.assertEqual(perfis[0]["mapeamento"], mapeamento)
        self.assertTrue(perfis[0]["confirmado"])

    def test_engine_salva_e_reutiliza_mapeamento_confirmado(self):
        caminho = self.criar_planilha(
            "ambiguo.xlsx",
            [{
                "Nome": "Nome auxiliar",
                "Colaborador": "Ana",
                "Início": "01/08/2026",
                "Fim": "10/08/2026"
            }]
        )
        engine = ImportEngine(
            database_path=str(self.database),
            backups_root=str(self.root / "backups")
        )

        pendente = engine.analyze(str(caminho))
        confirmado = engine.analyze(
            str(caminho),
            mapeamento_confirmado={
                "nome": "Colaborador",
                "inicio": "Início",
                "fim": "Fim"
            }
        )
        reutilizado = engine.analyze(str(caminho))

        self.assertEqual(pendente["status"], "MAPEAMENTO_NECESSARIO")
        self.assertTrue(confirmado["pronta"])
        self.assertEqual(confirmado["mapeamento"]["origem"], "confirmado")
        self.assertTrue(reutilizado["pronta"])
        self.assertEqual(reutilizado["mapeamento"]["origem"], "salvo")

    def test_backup_e_hierarquico_consistente_e_nao_sobrescreve(self):
        servico = BackupService(str(self.root / "backups"))

        primeiro = Path(servico.before_import(str(self.database)))
        segundo = Path(servico.before_import(str(self.database)))

        self.assertNotEqual(primeiro, segundo)
        self.assertTrue(primeiro.is_file())
        self.assertEqual(len(primeiro.relative_to(self.root).parts), 5)
        conn = sqlite3.connect(primeiro)
        valor = conn.execute("SELECT valor FROM controle").fetchone()[0]
        conn.close()
        self.assertEqual(valor, "original")

    def test_audit_service_e_dashboard_updater_sao_independentes(self):
        AuditService(str(self.database)).record(
            "Teste de auditoria",
            "Executado sem Flask",
            user="Teste",
            ip="127.0.0.1"
        )
        updater = DashboardUpdater(str(self.database))
        atualizacoes = updater.update_all(3)

        conn = sqlite3.connect(self.database)
        auditoria = conn.execute(
            "SELECT acao, usuario FROM auditoria"
        ).fetchone()
        modulos = conn.execute(
            """
            SELECT modulo, versao_importacao
            FROM atualizacoes_modulos ORDER BY modulo
            """
        ).fetchall()
        conn.close()

        self.assertEqual(auditoria, ("Teste de auditoria", "Teste"))
        self.assertEqual(len(atualizacoes), 4)
        self.assertEqual(len(modulos), 4)
        self.assertTrue(all(versao == 3 for _, versao in modulos))

    def test_plugins_respeitam_prioridade_e_ativacao(self):
        chamadas = []

        class PrimeiroPlugin(ImportPlugin):
            name = "primeiro"
            hooks = ("arquivo_lido",)
            priority = 200

            def execute(self, context):
                chamadas.append(self.name)

        class SegundoPlugin(ImportPlugin):
            name = "segundo"
            hooks = ("arquivo_lido",)
            priority = 100

            def execute(self, context):
                chamadas.append(self.name)

        manager = ImportPluginManager(
            str(self.database),
            str(self.root / "plugins")
        )
        manager.register(PrimeiroPlugin())
        manager.register(SegundoPlugin())
        manager.dispatch("arquivo_lido", ImportPluginContext())
        manager.configure("segundo", enabled=False)
        manager.dispatch("arquivo_lido", ImportPluginContext())

        self.assertEqual(chamadas, ["segundo", "primeiro", "primeiro"])

    def test_plugin_nao_critico_e_isolado_e_critico_interrompe(self):
        class FalhaSegura(ImportPlugin):
            name = "falha_segura"
            hooks = ("dados_validados",)
            critical = False

            def execute(self, context):
                raise RuntimeError("falha controlada")

        class FalhaCritica(ImportPlugin):
            name = "falha_critica"
            hooks = ("backup_criado", "dados_salvos")
            critical = True

            def execute(self, context):
                raise RuntimeError("falha crítica")

        manager = ImportPluginManager(
            str(self.database),
            str(self.root / "plugins")
        )
        manager.register(FalhaSegura())
        manager.register(FalhaCritica())

        resultado = manager.dispatch(
            "dados_validados",
            ImportPluginContext()
        )

        self.assertEqual(resultado[0]["resultado"], "Falha")
        with self.assertRaises(PluginExecutionError):
            manager.dispatch("backup_criado", ImportPluginContext())
        pos_gravacao = manager.dispatch(
            "dados_salvos",
            ImportPluginContext()
        )
        self.assertEqual(pos_gravacao[0]["resultado"], "Falha")

    def test_plugin_manager_descobre_arquivo_sem_alterar_nucleo(self):
        plugins_dir = self.root / "plugins"
        plugins_dir.mkdir()
        (plugins_dir / "customizado.py").write_text(
            "\n".join([
                "from services.import_plugin import ImportPlugin",
                "class Customizado(ImportPlugin):",
                "    name = 'customizado'",
                "    hooks = ('importacao_concluida',)",
                "    def execute(self, context):",
                "        return {'filial': 'Goiás'}",
                "def register_plugins(manager):",
                "    manager.register(Customizado(), source=__file__)",
            ]),
            encoding="utf-8"
        )
        manager = ImportPluginManager(
            str(self.database),
            str(plugins_dir)
        )

        carregados = manager.discover()
        execucoes = manager.dispatch(
            "importacao_concluida",
            ImportPluginContext(filename="ferias.xlsx")
        )

        self.assertEqual(carregados, ["customizado"])
        self.assertEqual(
            execucoes[0]["retorno"],
            {"filial": "Goiás"}
        )
        self.assertFalse(manager.load_errors)

    def test_logger_registra_falha_sucesso_e_versionamento(self):
        logger = ImportLogger(str(self.database))
        logger.record_failure(
            arquivo="invalida.xlsx",
            quantidade=2,
            tempo_segundos=0.2,
            erros=2,
            usuario="T.Costa",
            ip="127.0.0.1"
        )
        versao = logger.record_success(
            arquivo="valida.xlsx",
            registros=83,
            erros=0,
            duracao_segundos=1.3,
            usuario="T.Costa",
            ip="127.0.0.1",
            comparacao={
                "novos": 3,
                "removidos": 1,
                "alterados": 2,
                "iguais": 77
            },
            hash_arquivo="hash"
        )

        conn = sqlite3.connect(self.database)
        logs = conn.execute(
            """
            SELECT arquivo, quantidade, erros, versao, ip, resultado
            FROM importacao_logs ORDER BY id
            """
        ).fetchall()
        importacao = conn.execute(
            """
            SELECT versao, novos, removidos, datas_alteradas, sem_alteracoes
            FROM importacoes
            """
        ).fetchone()
        conn.close()

        self.assertEqual(versao, 1)
        self.assertEqual(logs[0], (
            "invalida.xlsx", 2, 2, None, "127.0.0.1", "Falha"
        ))
        self.assertEqual(logs[1], (
            "valida.xlsx", 83, 0, 1, "127.0.0.1", "Sucesso"
        ))
        self.assertEqual(importacao, (1, 3, 1, 2, 77))

    def test_engine_publica_eventos_sem_conhecer_a_tela(self):
        caminho = self.criar_planilha(
            "ferias.xlsx",
            [{
                "Nome": "Ana",
                "Inicio": "01/08/2026",
                "Fim": "10/08/2026"
            }]
        )
        eventos = []
        event_bus = EventBus()
        event_bus.subscribe(
            "planilha_validada",
            lambda payload: eventos.append(("validada", payload))
        )
        event_bus.subscribe(
            "importacao_concluida",
            lambda payload: eventos.append(("concluida", payload))
        )
        engine = ImportEngine(
            database_path=str(self.database),
            backups_root=str(self.root / "backups"),
            event_bus=event_bus
        )

        resultado = engine.analyze(str(caminho))
        engine.record_validation(
            resultado=resultado,
            tempo_segundos=0.1,
            usuario="T.Costa",
            ip="127.0.0.1"
        )
        backup = engine.prepare_import()
        versao = engine.complete(
            caminho_arquivo=str(caminho),
            arquivo=caminho.name,
            registros=resultado["total_registros"],
            duracao_segundos=0.2,
            usuario="T.Costa",
            ip="127.0.0.1",
            comparacao=resultado["comparacao"],
            backup=backup
        )

        self.assertEqual(versao, 1)
        self.assertEqual(
            [nome for nome, _ in eventos],
            ["validada", "concluida"]
        )
        self.assertEqual(eventos[1][1]["backup"], backup)

    def test_import_service_executa_plugins_em_todo_fluxo(self):
        hooks = []

        class Rastreador(ImportPlugin):
            name = "rastreador_fluxo"
            hooks = (
                "importacao_iniciada",
                "arquivo_lido",
                "colunas_mapeadas",
                "dados_validados",
                "comparacao_concluida",
                "backup_criado",
                "dados_salvos",
                "auditoria_registrada",
                "dashboard_atualizado",
                "importacao_concluida",
            )

            def execute(self, context):
                hooks.append(context.hook)

        caminho = self.criar_planilha(
            "pipeline.xlsx",
            [{
                "Nome": "Ana",
                "Início": "01/08/2026",
                "Fim": "10/08/2026"
            }]
        )
        manager = ImportPluginManager(
            str(self.database),
            str(self.root / "plugins")
        )
        manager.register(Rastreador())
        service = ImportService(
            database_path=str(self.database),
            backups_root=str(self.root / "backups"),
            plugin_manager=manager
        )

        resultado = service.analyze(str(caminho))
        service.record_validation(
            resultado=resultado,
            tempo_segundos=0.1,
            usuario="T.Costa",
            ip="127.0.0.1"
        )
        backup = service.prepare_import(
            operation_id=resultado["operacao_id"],
            filename=caminho.name,
            user="T.Costa",
            ip="127.0.0.1"
        )
        service.complete(
            caminho_arquivo=str(caminho),
            arquivo=caminho.name,
            registros=resultado["total_registros"],
            duracao_segundos=0.2,
            usuario="T.Costa",
            ip="127.0.0.1",
            comparacao=resultado["comparacao"],
            backup=backup,
            operation_id=resultado["operacao_id"]
        )

        self.assertEqual(hooks, [
            "importacao_iniciada",
            "arquivo_lido",
            "colunas_mapeadas",
            "dados_validados",
            "comparacao_concluida",
            "auditoria_registrada",
            "backup_criado",
            "dados_salvos",
            "auditoria_registrada",
            "dashboard_atualizado",
            "importacao_concluida",
        ])


class ImportRouteIntegrationTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.database = self.root / "fokus.db"
        self.uploads = self.root / "uploads"
        self.validacoes = self.root / "validacoes"
        self.backups = self.root / "backups"
        self.uploads.mkdir()
        self.originals = {
            "DATABASE_PATH": sistema.DATABASE_PATH,
            "UPLOAD_FOLDER": sistema.UPLOAD_FOLDER,
            "VALIDACOES_DIR": sistema.VALIDACOES_DIR,
            "BACKUPS_DIR": sistema.BACKUPS_DIR,
            "pasta_padrao": sistema.CONFIGURACOES_PADRAO["pasta_padrao"]
        }
        sistema.DATABASE_PATH = str(self.database)
        sistema.UPLOAD_FOLDER = str(self.uploads)
        sistema.VALIDACOES_DIR = str(self.validacoes)
        sistema.BACKUPS_DIR = str(self.backups)
        sistema.CONFIGURACOES_PADRAO["pasta_padrao"] = str(self.uploads)
        sistema.app.config.update(TESTING=True)
        sistema.inicializar_tabelas_sistema()
        self.client = sistema.app.test_client()

    def tearDown(self):
        sistema.DATABASE_PATH = self.originals["DATABASE_PATH"]
        sistema.UPLOAD_FOLDER = self.originals["UPLOAD_FOLDER"]
        sistema.VALIDACOES_DIR = self.originals["VALIDACOES_DIR"]
        sistema.BACKUPS_DIR = self.originals["BACKUPS_DIR"]
        sistema.CONFIGURACOES_PADRAO["pasta_padrao"] = self.originals[
            "pasta_padrao"
        ]
        self.temp_dir.cleanup()

    def test_fluxo_validacao_backup_importacao_log_e_eventos(self):
        arquivo = self.root / "Ferias_Agosto.xlsx"
        pd.DataFrame([{
            "Nome": "Ana",
            "Inicio": "01/08/2026",
            "Fim": "10/08/2026",
            "Departamento": "RH",
            "Matrícula": "100"
        }]).to_excel(arquivo, index=False)

        resposta_validacao = self.client.post(
            "/api/importacao/validar",
            data={
                "arquivo": (
                    io.BytesIO(arquivo.read_bytes()),
                    arquivo.name
                )
            },
            content_type="multipart/form-data",
            headers={"X-Forwarded-For": "10.0.0.10"}
        )
        payload = resposta_validacao.get_json()

        self.assertEqual(resposta_validacao.status_code, 200)
        self.assertTrue(payload["validacao"]["pronta"])
        resposta_importacao = self.client.post(
            "/upload",
            data={"validacao_token": payload["token"]},
            headers={"X-Forwarded-For": "10.0.0.10"}
        )

        self.assertEqual(resposta_importacao.status_code, 200)
        self.assertTrue((self.uploads / arquivo.name).is_file())
        backups = list(self.backups.rglob("backup_*.db"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(
            len(backups[0].relative_to(self.backups).parts),
            4
        )

        conn = sqlite3.connect(self.database)
        log = conn.execute(
            """
            SELECT arquivo, quantidade, erros, versao, ip, resultado
            FROM importacao_logs
            """
        ).fetchone()
        versao = conn.execute(
            "SELECT versao, arquivo, registros FROM importacoes"
        ).fetchone()
        auditorias = conn.execute(
            "SELECT acao, resultado FROM auditoria ORDER BY id"
        ).fetchall()
        atualizacoes = conn.execute(
            """
            SELECT modulo, versao_importacao
            FROM atualizacoes_modulos ORDER BY modulo
            """
        ).fetchall()
        conn.close()

        self.assertEqual(log, (
            arquivo.name, 1, 0, 1, "10.0.0.10", "Sucesso"
        ))
        self.assertEqual(versao, (1, arquivo.name, 1))
        self.assertIn(("Validou planilha", "Sucesso"), auditorias)
        self.assertIn(("Importou planilha", "Sucesso"), auditorias)
        self.assertIn(
            ("Backup antes da importação", "Sucesso"),
            auditorias
        )
        self.assertEqual(
            sum(1 for acao, _ in auditorias if acao == "Importou planilha"),
            1
        )
        self.assertEqual(len(atualizacoes), 4)
        self.assertTrue(all(versao == 1 for _, versao in atualizacoes))
        status_modulos = self.client.get(
            "/api/importacao/atualizacoes"
        ).get_json()
        self.assertEqual(len(status_modulos["modulos"]), 4)

    def test_simulacao_exibe_resumo_sem_alterar_banco_ou_dashboard(self):
        arquivo = self.root / "Ferias_Simulacao.xlsx"
        pd.DataFrame([
            {
                "Nome": "Ana",
                "Inicio": "01/08/2026",
                "Fim": "10/08/2026",
                "Departamento": "RH",
                "Matrícula": "100"
            },
            {
                "Nome": "Bruno",
                "Inicio": "05/08/2026",
                "Fim": "18/09/2026",
                "Departamento": "Operações",
                "Matrícula": "200"
            }
        ]).to_excel(arquivo, index=False)

        # Inicializa estruturas que fazem parte da subida normal da aplicação.
        sistema.obter_motor_importacao()
        conn = sqlite3.connect(self.database)
        antes = "\n".join(conn.iterdump())
        conn.close()

        resposta = self.client.post(
            "/api/importacao/validar",
            data={
                "modo": "simulacao",
                "arquivo": (
                    io.BytesIO(arquivo.read_bytes()),
                    arquivo.name
                )
            },
            content_type="multipart/form-data"
        )
        payload = resposta.get_json()

        conn = sqlite3.connect(self.database)
        depois = "\n".join(conn.iterdump())
        conn.close()

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(payload["validacao"]["simulacao"])
        self.assertTrue(payload["validacao"]["pronta"])
        self.assertEqual(
            payload["validacao"]["resumo"]["usuarios_unicos"],
            2
        )
        self.assertEqual(
            payload["validacao"]["resumo"]["departamentos"],
            2
        )
        self.assertEqual(
            payload["validacao"]["resumo"]["periodo"],
            {"inicio": "01/08/2026", "fim": "18/09/2026"}
        )
        self.assertEqual(antes, depois)
        self.assertFalse((self.uploads / arquivo.name).exists())
        self.assertEqual(list(self.backups.rglob("backup_*.db")), [])

        confirmacao = self.client.post(
            "/upload",
            data={"validacao_token": payload["token"]}
        )
        self.assertEqual(confirmacao.status_code, 400)
        self.assertFalse((self.uploads / arquivo.name).exists())

    def test_endpoint_confirma_e_persiste_mapeamento_ambiguo(self):
        arquivo = self.root / "Ferias_Modelo_Ambiguo.xlsx"
        pd.DataFrame([{
            "Nome": "Referência",
            "Colaborador": "Ana",
            "Início das Férias": "01/08/2026",
            "Retorno": "10/08/2026"
        }]).to_excel(arquivo, index=False)

        resposta_inicial = self.client.post(
            "/api/importacao/validar",
            data={
                "arquivo": (
                    io.BytesIO(arquivo.read_bytes()),
                    arquivo.name
                )
            },
            content_type="multipart/form-data"
        )
        inicial = resposta_inicial.get_json()

        self.assertEqual(
            inicial["validacao"]["status"],
            "MAPEAMENTO_NECESSARIO"
        )
        resposta_confirmacao = self.client.post(
            "/api/importacao/mapeamento",
            json={
                "token": inicial["token"],
                "mapeamento": {
                    "nome": "Colaborador",
                    "inicio": "Início das Férias",
                    "fim": "Retorno"
                },
                "nome_perfil": "RH Goiás",
                "origem": "Goiás"
            }
        )
        confirmado = resposta_confirmacao.get_json()

        self.assertEqual(resposta_confirmacao.status_code, 200)
        self.assertTrue(confirmado["validacao"]["pronta"])
        self.assertEqual(
            confirmado["validacao"]["mapeamento"]["origem"],
            "confirmado"
        )
        resposta_importacao = self.client.post(
            "/upload",
            data={"validacao_token": inicial["token"]}
        )
        self.assertEqual(resposta_importacao.status_code, 200)
        self.assertTrue(
            (self.uploads / arquivo.name).is_file(),
            (
                f"Arquivos: {[item.name for item in self.uploads.iterdir()]}; "
                f"Resposta: {resposta_importacao.get_data(as_text=True)[:2000]}"
            )
        )
        conn = sqlite3.connect(self.database)
        total = conn.execute(
            "SELECT COUNT(*) FROM perfis_importacao"
        ).fetchone()[0]
        conn.close()
        self.assertEqual(total, 1)
        self.assertEqual(
            confirmado["validacao"]["perfil_importacao"]["nome"],
            "RH Goiás"
        )

    def test_api_lista_renomeia_e_desativa_perfil(self):
        store = ImportProfileStore(str(self.database))
        perfil = store.save(
            ["Colaborador", "Início", "Retorno"],
            {
                "nome": "Colaborador",
                "inicio": "Início",
                "fim": "Retorno"
            },
            nome="RH Goiás",
            confirmado=True
        )

        listagem = self.client.get("/api/importacao/perfis").get_json()
        alteracao = self.client.patch(
            f"/api/importacao/perfis/{perfil['id']}",
            json={"nome": "RH Centro-Oeste", "ativo": False}
        )
        incluindo_inativos = self.client.get(
            "/api/importacao/perfis?incluir_inativos=1"
        ).get_json()

        self.assertEqual(len(listagem["perfis"]), 1)
        self.assertEqual(alteracao.status_code, 200)
        self.assertEqual(
            incluindo_inativos["perfis"][0]["nome"],
            "RH Centro-Oeste"
        )
        self.assertFalse(incluindo_inativos["perfis"][0]["ativo"])

    def test_api_lista_e_configura_plugin_sem_tela(self):
        listagem = self.client.get(
            "/api/importacao/plugins"
        ).get_json()
        nomes = {plugin["nome"] for plugin in listagem["plugins"]}

        self.assertIn("notificacao_erro_exemplo", nomes)
        resposta = self.client.patch(
            "/api/importacao/plugins/notificacao_erro_exemplo",
            json={"ativo": True, "prioridade": 50}
        )
        atualizada = self.client.get(
            "/api/importacao/plugins"
        ).get_json()
        plugin = next(
            item
            for item in atualizada["plugins"]
            if item["nome"] == "notificacao_erro_exemplo"
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(plugin["ativo"])
        self.assertEqual(plugin["prioridade"], 50)


if __name__ == "__main__":
    unittest.main()
