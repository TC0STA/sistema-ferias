"""Lógica compartilhada do backend do Fokus Férias.

Não registra rotas Flask.
"""


from flask import Flask, render_template, request, send_from_directory, send_file, redirect, url_for


import pandas as pd


import os


import sqlite3


import unicodedata


import calendar as calendar_module


import csv


import json


import zipfile


import shutil


import time


import uuid


from io import BytesIO


from io import StringIO


from datetime import datetime, timedelta


from urllib.parse import quote


from services.events import EventBus


from services.audit_service import AuditService


from services.column_alias_store import ColumnAliasStore


from services.import_service import ImportService


from services.import_plugin import PluginExecutionError


UPLOAD_FOLDER = "uploads"


DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "ferias.db")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))


VALIDACOES_DIR = os.path.join(BASE_DIR, "uploads", ".validacoes")


BACKUPS_DIR = os.path.join(BASE_DIR, "backups")


IMPORT_EVENTS = EventBus()


CONFIGURACOES_PADRAO = {
    "nome_empresa": "Grupo Fokus Logística",
    "nome_sistema": "Fokus Férias",
    "versao": "2.0",
    "banco": "SQLite",
    "ambiente": "Produção",
    "notificacoes_ativas": "1",
    "hora_rotina": "08:00",
    "dias_antes_bloqueio": "3",
    "som_notificacoes": "1",
    "pasta_padrao": "uploads",
    "substituir_planilha": "0",
    "validar_planilha": "1",
    "mostrar_resumo_importacao": "1",
    "backup_antes_importacao": "1",
    "mostrar_popup": "1",
    "notificar_importacao": "1",
    "tema": "claro",
    "cor_principal": "azul-fokus",
    "tamanho_fonte": "normal",
    "pdf_logo": "1",
    "pdf_rodape": "1",
    "pdf_numero_pagina": "1",
    "pdf_data": "1",
    "excel_autofiltro": "1",
    "excel_ajustar_colunas": "1",
    "excel_congelar_cabecalho": "1",
    "limpeza_backups": "1",
    "manter_backups": "10"
}


def inicializar_tabelas_sistema():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT NOT NULL,
            acao TEXT NOT NULL,
            detalhe TEXT,
            usuario TEXT NOT NULL,
            ip TEXT
        )
    """)
    colunas_auditoria = {
        item[1] for item in cursor.execute("PRAGMA table_info(auditoria)").fetchall()
    }
    if "ip" not in colunas_auditoria:
        cursor.execute("ALTER TABLE auditoria ADD COLUMN ip TEXT")
    if "resultado" not in colunas_auditoria:
        cursor.execute(
            "ALTER TABLE auditoria ADD COLUMN resultado TEXT NOT NULL DEFAULT 'Sucesso'"
        )
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT NOT NULL,
            atualizado_em TEXT NOT NULL
        )
    """)
    agora = datetime.now().isoformat()
    for chave, valor in CONFIGURACOES_PADRAO.items():
        cursor.execute(
            "INSERT OR IGNORE INTO configuracoes (chave, valor, atualizado_em) VALUES (?, ?, ?)",
            (chave, valor, agora)
        )
    conn.commit()
    conn.close()
    ColumnAliasStore(DATABASE_PATH).ensure_schema()


def registrar_auditoria(
    acao, detalhe="", usuario=None, ip=None, resultado="Sucesso"
):
    if usuario is None:
        try:
            from services.auth_service import current_actor
            usuario = current_actor()
        except (ImportError, RuntimeError):
            usuario = "Sistema"
    inicializar_tabelas_sistema()
    if ip is None:
        try:
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "Local")
            ip = ip.split(",")[0].strip()
        except RuntimeError:
            ip = "Local"
    AuditService(DATABASE_PATH).record(
        acao,
        detalhe,
        user=usuario,
        ip=ip,
        result=resultado
    )


def obter_ip_requisicao():
    try:
        ip = request.headers.get("X-Forwarded-For", request.remote_addr or "Local")
        return ip.split(",")[0].strip()
    except RuntimeError:
        return "Local"


def obter_motor_importacao(*, readonly=False):
    return ImportService(
        database_path=DATABASE_PATH,
        backups_root=BACKUPS_DIR,
        event_bus=IMPORT_EVENTS,
        persist_plugin_registry=not readonly
    )


def auditar_importacao_concluida(evento):
    for nome in evento.get("bloqueios_registrados", []):
        registrar_auditoria(
            "Executou bloqueio",
            f"Colaborador: {nome}",
            usuario=evento["usuario"],
            ip=evento["ip"]
        )


IMPORT_EVENTS.subscribe(
    "importacao_concluida",
    auditar_importacao_concluida
)


def carregar_configuracoes():
    inicializar_tabelas_sistema()
    conn = sqlite3.connect(DATABASE_PATH)
    valores = dict(conn.execute("SELECT chave, valor FROM configuracoes").fetchall())
    conn.close()
    return {**CONFIGURACOES_PADRAO, **valores}


def obter_pasta_planilhas():
    pasta = carregar_configuracoes().get("pasta_padrao", UPLOAD_FOLDER).strip()
    caminho = pasta if os.path.isabs(pasta) else os.path.join(BASE_DIR, pasta)
    os.makedirs(caminho, exist_ok=True)
    return caminho


def listar_backups():
    pasta = BACKUPS_DIR
    if not os.path.isdir(pasta):
        return []
    arquivos = []
    for raiz, _, nomes in os.walk(pasta):
        arquivos.extend(
            os.path.join(raiz, nome)
            for nome in nomes
            if nome.lower().endswith((".zip", ".db"))
        )
    return sorted(arquivos, key=os.path.getmtime, reverse=True)


def criar_backup(origem="manual"):
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    nome_arquivo = f"backup_ferias_{datetime.now():%Y%m%d_%H%M%S_%f}.zip"
    caminho_backup = os.path.join(BACKUPS_DIR, nome_arquivo)
    configuracoes_atuais = carregar_configuracoes()

    with zipfile.ZipFile(caminho_backup, "w", zipfile.ZIP_DEFLATED) as arquivo:
        if os.path.exists(DATABASE_PATH):
            arquivo.write(DATABASE_PATH, "database/ferias.db")
        arquivo.writestr(
            "configuracoes/configuracoes.json",
            json.dumps(configuracoes_atuais, ensure_ascii=False, indent=2)
        )
        pasta_logs = os.path.join(BASE_DIR, "logs")
        if os.path.isdir(pasta_logs):
            for raiz, _, nomes in os.walk(pasta_logs):
                for nome in nomes:
                    caminho_log = os.path.join(raiz, nome)
                    relativo = os.path.relpath(caminho_log, pasta_logs)
                    arquivo.write(caminho_log, os.path.join("logs", relativo))

    if configuracoes_atuais.get("limpeza_backups") == "1":
        try:
            manter = max(1, int(configuracoes_atuais.get("manter_backups", "10")))
        except ValueError:
            manter = 10
        for antigo in listar_backups()[manter:]:
            os.remove(antigo)

    registrar_auditoria(
        "Backup",
        f"Backup {origem}: {nome_arquivo}",
        usuario="Sistema" if origem == "automático" else None
    )
    return caminho_backup


def limpar_backups_antigos():
    configuracoes = carregar_configuracoes()
    try:
        manter = max(1, int(configuracoes.get("manter_backups", "10")))
    except ValueError:
        manter = 10
    removidos = 0
    for caminho in listar_backups()[manter:]:
        os.remove(caminho)
        removidos += 1
    return removidos


def obter_saude_sistema():
    pasta = obter_pasta_planilhas()
    caminho_planilha = planilha_mais_recente()
    backups = listar_backups()
    agora = datetime.now()
    itens = []

    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.execute("SELECT 1").fetchone()
        conn.close()
        itens.append(("Banco SQLite", "Funcionando", "ok", "database"))
    except sqlite3.Error:
        itens.append(("Banco SQLite", "Falha na conexão", "error", "database"))

    if os.path.isdir(pasta):
        itens.append(("Pasta uploads", "OK", "ok", "folder-check"))
    else:
        itens.append(("Pasta uploads", "Não encontrada", "error", "folder-x"))

    permissao = os.access(pasta, os.R_OK | os.W_OK)
    itens.append((
        "Permissões", "OK" if permissao else "Sem acesso de escrita",
        "ok" if permissao else "error", "shield-check"
    ))

    if caminho_planilha:
        momento = datetime.fromtimestamp(os.path.getmtime(caminho_planilha))
        dias = (agora - momento).days
        nivel = "ok" if dias <= 7 else "warning"
        texto = "Sucesso" if dias <= 7 else "Nenhuma planilha nesta semana"
        itens.append(("Última importação", texto, nivel, "file-check-2"))
    else:
        itens.append((
            "Última importação", "Nenhuma planilha importada",
            "warning", "file-warning"
        ))

    if backups:
        momento = datetime.fromtimestamp(os.path.getmtime(backups[0]))
        dias = (agora - momento).days
        nivel = "ok" if dias <= 30 else "error"
        texto = "Atualizado" if dias <= 30 else "Há mais de 30 dias"
        itens.append(("Backup", texto, nivel, "database-backup"))
    else:
        itens.append(("Backup", "Ainda não realizado", "error", "database-zap"))

    livres = shutil.disk_usage(BASE_DIR).free / (1024 ** 3)
    espaco_texto = f"{livres:.1f}".replace(".", ",")
    itens.append(("Espaço em disco", f"{espaco_texto} GB livres", "ok", "hard-drive"))
    return [
        {"nome": nome, "status": status, "nivel": nivel, "icone": icone}
        for nome, status, nivel, icone in itens
    ]


def normalizar_texto(valor):
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )


def contem_palavra(texto, palavras):
    return any(palavra in texto for palavra in palavras)


def encontrar_coluna(df, opcoes):
    for coluna in df.columns:
        coluna_normalizada = normalizar_texto(coluna)

        if coluna_normalizada in opcoes:
            return coluna

    for coluna in df.columns:
        coluna_normalizada = normalizar_texto(coluna)

        if contem_palavra(coluna_normalizada, opcoes):
            return coluna

    return None


def _read_excel_sheet(caminho, sheet_name):
    bruto = pd.read_excel(caminho, sheet_name=sheet_name, header=None)

    for indice, row in bruto.iterrows():
        valores = [
            normalizar_texto(valor)
            for valor in row.tolist()
            if str(valor).strip().lower() != "nan"
        ]

        tem_nome = any(
            valor in [
                "nome", "funcionario", "colaborador", "usuario",
                "nome do colaborador", "nome do funcionario"
            ]
            for valor in valores
        )
        tem_inicio = any(
            valor in [
                "data inicio", "inicio", "inicio das ferias",
                "inicio ferias", "ferias inicio", "data inicial",
                "data de inicio"
            ] or "inicio" in valor
            for valor in valores
        )
        tem_fim = any(
            valor in [
                "data fim", "fim", "retorno", "data retorno", "volta",
                "fim das ferias", "fim ferias", "data final", "data de fim"
            ] or "fim" in valor
            for valor in valores
        )

        if tem_nome and tem_inicio and tem_fim:
            df = pd.read_excel(caminho, sheet_name=sheet_name, header=indice)
            df.columns = df.columns.str.strip()
            return df

    df = pd.read_excel(caminho, sheet_name=sheet_name)
    df.columns = df.columns.str.strip()
    return df


def ler_excel_com_cabecalho(caminho):
    excel = pd.ExcelFile(caminho)
    dataframes = []

    for sheet_name in excel.sheet_names:
        df = _read_excel_sheet(caminho, sheet_name)
        if not df.empty:
            dataframes.append(df)

    if not dataframes:
        df = pd.read_excel(caminho)
        df.columns = df.columns.str.strip()
        return df

    if len(dataframes) == 1:
        return dataframes[0]

    return pd.concat(dataframes, ignore_index=True, sort=False)


def carregar_planilha(caminho, mapeamento=None):
    df = ler_excel_com_cabecalho(caminho)

    mapeamento = mapeamento or {}
    coluna_nome = mapeamento.get("nome") or encontrar_coluna(
        df,
        [
            "nome", "funcionario", "colaborador", "usuario",
            "nome do colaborador", "nome do funcionario"
        ]
    )
    coluna_inicio = mapeamento.get("inicio") or encontrar_coluna(
        df,
        [
            "inicio", "inicio ferias", "inicio das ferias", "data inicio",
            "data de inicio", "ferias inicio", "data inicial"
        ]
    )
    coluna_fim = mapeamento.get("fim") or encontrar_coluna(
        df,
        [
            "fim", "fim ferias", "fim das ferias", "data fim",
            "data de fim", "retorno", "data retorno", "volta", "data final"
        ]
    )
    coluna_bloqueio = encontrar_coluna(
        df,
        ["data de bloqueio", "bloqueio", "data bloqueio"]
    )

    if coluna_nome is None or coluna_inicio is None or coluna_fim is None:
        raise ValueError(
            "A planilha precisa ter colunas de Nome, Inicio e Fim."
        )

    colunas = {
        coluna_nome: "Nome",
        coluna_inicio: "Inicio",
        coluna_fim: "Fim"
    }

    if coluna_bloqueio is not None:
        colunas[coluna_bloqueio] = "Data de Bloqueio"

    for origem, destino in colunas.items():
        if (
            origem != destino
            and destino in df.columns
            and destino not in colunas
        ):
            df = df.drop(columns=[destino])
    df = df.rename(columns=colunas)

    df["Nome"] = df["Nome"].astype(str).str.strip()
    df = df[
        (df["Nome"] != "")
        & (df["Nome"].str.lower() != "nan")
    ].copy()

    df["Inicio"] = pd.to_datetime(
        df["Inicio"],
        errors="coerce",
        dayfirst=True
    )

    df["Fim"] = pd.to_datetime(
        df["Fim"],
        errors="coerce",
        dayfirst=True
    )

    if "Data de Bloqueio" not in df.columns:
        dias_antes = int(
            carregar_configuracoes().get("dias_antes_bloqueio", "1")
        )
        df["Data de Bloqueio"] = df["Inicio"] - timedelta(days=dias_antes)

    df["Data de Bloqueio"] = pd.to_datetime(
        df["Data de Bloqueio"],
        errors="coerce",
        dayfirst=True
    )

    return df


def planilhas_importadas():
    pasta_planilhas = obter_pasta_planilhas()
    arquivos = [
        os.path.join(pasta_planilhas, nome)
        for nome in os.listdir(pasta_planilhas)
        if nome.lower().endswith((".xlsx", ".xls"))
    ]
    return sorted(arquivos, key=os.path.getmtime)


def planilha_mais_recente():
    arquivos = planilhas_importadas()
    if not arquivos:
        return None
    return arquivos[-1]


def carregar_planilhas(caminhos, mapeamento=None):
    frames = []
    for caminho in caminhos:
        try:
            df = carregar_planilha(caminho, mapeamento=mapeamento)
        except Exception:
            continue
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["Nome", "Inicio", "Fim", "Data de Bloqueio"])

    df = pd.concat(frames, ignore_index=True, sort=False)
    if {"Nome", "Inicio", "Fim", "Data de Bloqueio"}.issubset(df.columns):
        df = df.drop_duplicates(subset=["Nome", "Inicio", "Fim", "Data de Bloqueio"])
    return df.reset_index(drop=True)


def limpar_validacoes_temporarias(limite_segundos=3600):
    os.makedirs(VALIDACOES_DIR, exist_ok=True)
    agora = time.time()
    for nome in os.listdir(VALIDACOES_DIR):
        caminho = os.path.join(VALIDACOES_DIR, nome)
        if (
            os.path.isfile(caminho)
            and agora - os.path.getmtime(caminho) > limite_segundos
        ):
            os.remove(caminho)


def token_validacao_seguro(token):
    return (
        isinstance(token, str)
        and len(token) == 32
        and all(caractere in "0123456789abcdef" for caractere in token)
    )


def caminho_metadados_validacao(token):
    return os.path.join(VALIDACOES_DIR, f"{token}.json")


def carregar_validacao_temporaria(token):
    if not token_validacao_seguro(token):
        return None
    caminho_metadados = caminho_metadados_validacao(token)
    if not os.path.isfile(caminho_metadados):
        return None
    try:
        with open(caminho_metadados, "r", encoding="utf-8") as arquivo:
            metadados = json.load(arquivo)
    except (OSError, json.JSONDecodeError):
        return None
    extensao = metadados.get("extensao", "")
    caminho = os.path.join(VALIDACOES_DIR, f"{token}{extensao}")
    if not os.path.isfile(caminho):
        return None
    metadados["caminho"] = caminho
    metadados["caminho_metadados"] = caminho_metadados
    return metadados


def formatar_datas(df):
    df = df.copy()

    for coluna in ["Inicio", "Fim", "Data de Bloqueio"]:
        if coluna in df.columns:
            df[coluna] = df[coluna].dt.strftime("%d/%m/%Y")
            df[coluna] = df[coluna].fillna("")

    return df


def obter_dados_relatorios():
    agora = datetime.now()
    hoje = agora.date()
    periodo = request.args.get("periodo", agora.strftime("%Y-%m"))
    departamento_filtro = request.args.get("departamento", "").strip()
    status_filtro = request.args.get("status", "").strip()
    pesquisa = request.args.get("q", "").strip()

    try:
        ano_selecionado, mes_selecionado = [int(parte) for parte in periodo.split("-", 1)]
        primeiro_dia = datetime(ano_selecionado, mes_selecionado, 1).date()
    except (TypeError, ValueError):
        ano_selecionado, mes_selecionado = hoje.year, hoje.month
        periodo = agora.strftime("%Y-%m")
        primeiro_dia = hoje.replace(day=1)

    ultimo_dia = (
        datetime(ano_selecionado + 1, 1, 1).date()
        if mes_selecionado == 12
        else datetime(ano_selecionado, mes_selecionado + 1, 1).date()
    ) - timedelta(days=1)

    colaboradores = obter_colaboradores()
    departamentos = sorted({
        item["departamento"] for item in colaboradores
        if item["departamento"] != "Não informado"
    })

    if departamento_filtro:
        colaboradores = [
            item for item in colaboradores
            if item["departamento"] == departamento_filtro
        ]
    if pesquisa:
        pesquisa_normalizada = normalizar_texto(pesquisa)
        colaboradores = [
            item for item in colaboradores
            if pesquisa_normalizada in normalizar_texto(item["nome"])
        ]
    if status_filtro:
        colaboradores = [
            item for item in colaboradores
            if item["status_classe"] == status_filtro
        ]

    registros = []
    for colaborador in colaboradores:
        for periodo_ferias in colaborador["periodos"]:
            inicio = periodo_ferias["inicio"]
            fim = periodo_ferias["fim"]
            status_classe = (
                "active" if inicio <= hoje <= fim
                else "scheduled" if inicio > hoje
                else "completed"
            )
            status = {
                "active": "Em férias",
                "scheduled": "Programada",
                "completed": "Concluída"
            }[status_classe]
            registros.append({
                "nome": colaborador["nome"],
                "departamento": colaborador["departamento"],
                "inicio": inicio,
                "fim": fim,
                "bloqueio": periodo_ferias["bloqueio"],
                "status": status,
                "status_classe": status_classe,
                "dias": (fim - inicio).days + 1
            })

    registros_periodo = [
        item for item in registros
        if item["inicio"] <= ultimo_dia and item["fim"] >= primeiro_dia
    ]

    nomes_filtrados = {item["nome"] for item in colaboradores}
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bloqueios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            data_bloqueio TEXT,
            data_execucao TEXT
        )
    """)
    cursor.execute("SELECT nome, data_bloqueio, data_execucao FROM bloqueios")
    historico_bloqueios = cursor.fetchall()
    conn.close()
    historico_bloqueios = [
        item for item in historico_bloqueios
        if item[0] in nomes_filtrados
    ]

    nomes_meses = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
    ]
    ferias_por_mes = []
    bloqueios_por_mes = []
    for mes in range(1, 13):
        inicio_mes = datetime(ano_selecionado, mes, 1).date()
        fim_mes = (
            datetime(ano_selecionado + 1, 1, 1).date()
            if mes == 12
            else datetime(ano_selecionado, mes + 1, 1).date()
        ) - timedelta(days=1)
        ferias_por_mes.append(sum(
            1 for item in registros
            if item["inicio"] <= fim_mes and item["fim"] >= inicio_mes
        ))
        bloqueios_por_mes.append(sum(
            1 for _, data_bloqueio, _ in historico_bloqueios
            if str(data_bloqueio).startswith(f"{ano_selecionado}-{mes:02d}")
        ))

    departamentos_periodo = {}
    for item in registros_periodo:
        departamentos_periodo[item["departamento"]] = (
            departamentos_periodo.get(item["departamento"], 0) + 1
        )
    departamentos_ordenados = sorted(
        departamentos_periodo.items(),
        key=lambda item: (-item[1], normalizar_texto(item[0]))
    )

    status_contagem = {
        "active": sum(1 for item in colaboradores if item["status_classe"] == "active"),
        "scheduled": sum(1 for item in colaboradores if item["status_classe"] == "scheduled"),
        "completed": sum(1 for item in colaboradores if item["status_classe"] == "completed")
    }
    proximos_7_dias = [
        item for item in registros
        if hoje < item["inicio"] <= hoje + timedelta(days=7)
    ]
    proximos_bloqueios = [
        item for item in registros
        if item["bloqueio"] and item["bloqueio"] >= hoje
    ]
    retornos = [
        item for item in registros
        if item["fim"] >= hoje
    ]
    retornos_7_dias = [
        item for item in registros
        if hoje < item["fim"] <= hoje + timedelta(days=7)
    ]
    duracoes_regulares = [
        item["dias"] for item in registros_periodo
        if 1 <= item["dias"] <= 60
    ]
    maior_periodo = max(duracoes_regulares, default=0)
    departamentos_informados = [
        item for item in departamentos_ordenados
        if item[0] != "Não informado"
    ]
    mais_impactado = (
        departamentos_informados[0][0]
        if departamentos_informados else "Sem dados"
    )
    maior_volume = max(ferias_por_mes, default=0)
    mes_maior_volume = (
        nomes_meses[ferias_por_mes.index(maior_volume)]
        if maior_volume else "Sem dados"
    )
    percentual_em_ferias = (
        round((status_contagem["active"] / len(colaboradores)) * 100)
        if colaboradores else 0
    )
    caminho = planilha_mais_recente()
    ultima_atualizacao = (
        datetime.fromtimestamp(os.path.getmtime(caminho)).strftime("%d/%m/%Y")
        if caminho else "Sem importação"
    )

    periodos_disponiveis = set()
    for item in registros:
        cursor_mes = item["inicio"].replace(day=1)
        fim_cursor = item["fim"].replace(day=1)
        while cursor_mes <= fim_cursor:
            periodos_disponiveis.add(cursor_mes.strftime("%Y-%m"))
            cursor_mes = (
                cursor_mes.replace(year=cursor_mes.year + 1, month=1)
                if cursor_mes.month == 12
                else cursor_mes.replace(month=cursor_mes.month + 1)
            )
    periodos_disponiveis.add(periodo)

    return {
        "agora": agora,
        "periodo": periodo,
        "periodo_nome": f"{nomes_meses[mes_selecionado - 1]} de {ano_selecionado}",
        "departamento_filtro": departamento_filtro,
        "status_filtro": status_filtro,
        "pesquisa": pesquisa,
        "departamentos": departamentos,
        "periodos_disponiveis": [
            {
                "valor": valor,
                "rotulo": f"{nomes_meses[int(valor[5:7]) - 1]} {valor[:4]}"
            }
            for valor in sorted(periodos_disponiveis, reverse=True)
        ],
        "registros": registros_periodo,
        "total_colaboradores": len(colaboradores),
        "em_ferias": status_contagem["active"],
        "bloqueados": len(historico_bloqueios),
        "proximos": len(proximos_7_dias),
        "proximos_7_dias": len(proximos_7_dias),
        "retornos_7_dias": len(retornos_7_dias),
        "percentual_em_ferias": percentual_em_ferias,
        "mes_maior_volume": mes_maior_volume,
        "maior_volume": maior_volume,
        "meses": nomes_meses,
        "ferias_por_mes": ferias_por_mes,
        "bloqueios_por_mes": bloqueios_por_mes,
        "departamento_labels": [item[0] for item in departamentos_informados],
        "departamento_valores": [item[1] for item in departamentos_informados],
        "status_valores": [
            status_contagem["active"],
            status_contagem["scheduled"],
            status_contagem["completed"]
        ],
        "maior_periodo": maior_periodo,
        "proximo_bloqueio": min(
            (item["bloqueio"] for item in proximos_bloqueios),
            default=None
        ),
        "proximo_retorno": min(
            (item["fim"] for item in retornos),
            default=None
        ),
        "mais_impactado": mais_impactado,
        "ultima_atualizacao": ultima_atualizacao
    }


def obter_resumo_sistema():
    agora = datetime.now()
    hoje = agora.date()
    colaboradores = obter_colaboradores()
    caminhos = planilhas_importadas()
    caminho = planilha_mais_recente()
    bloqueios_hoje = 0
    inconsistencias = 0
    if caminhos:
        try:
            df = carregar_planilhas(caminhos)
            bloqueios_hoje = int(
                (df["Data de Bloqueio"].dt.date == hoje).sum()
            )
            inconsistencias = int(
                df["Inicio"].isna().sum()
                + df["Fim"].isna().sum()
                + ((df["Fim"] < df["Inicio"]) & df["Fim"].notna() & df["Inicio"].notna()).sum()
                + df.duplicated(subset=["Nome", "Inicio", "Fim"]).sum()
            )
        except (ValueError, OSError, KeyError):
            inconsistencias = 1

    periodos = [
        periodo
        for colaborador in colaboradores
        for periodo in colaborador["periodos"]
    ]
    retornos_hoje = sum(1 for item in periodos if item["fim"] == hoje)
    ferias_semana = sum(
        1 for item in periodos
        if hoje <= item["inicio"] <= hoje + timedelta(days=7)
    )
    proximos_bloqueios = sorted(
        item["bloqueio"] for item in periodos
        if item["bloqueio"] and item["bloqueio"] >= hoje
    )
    if agora.hour < 12:
        saudacao = "Bom dia"
    elif agora.hour < 18:
        saudacao = "Boa tarde"
    else:
        saudacao = "Boa noite"

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bloqueios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            data_bloqueio TEXT,
            data_execucao TEXT
        )
    """)
    bloqueados = cursor.execute("SELECT COUNT(*) FROM bloqueios").fetchone()[0]
    conn.close()

    return {
        "saudacao": saudacao,
        "total_colaboradores": len(colaboradores),
        "em_ferias": sum(1 for item in colaboradores if item["status_classe"] == "active"),
        "bloqueados": bloqueados,
        "bloqueios_hoje": bloqueios_hoje,
        "retornos_hoje": retornos_hoje,
        "ferias_semana": ferias_semana,
        "inconsistencias": inconsistencias,
        "proximo_bloqueio": proximos_bloqueios[0] if proximos_bloqueios else None,
        "planilha_nome": os.path.basename(caminho) if caminho else "Nenhuma planilha importada",
        "ultima_importacao_hora": (
            datetime.fromtimestamp(os.path.getmtime(caminho)).strftime("%H:%M")
            if caminho else "--:--"
        ),
        "ultima_importacao_data": (
            datetime.fromtimestamp(os.path.getmtime(caminho)).strftime("%d/%m/%Y")
            if caminho else "Sem importação"
        )
    }


def obter_timeline_sistema(limite=6):
    inicializar_tabelas_sistema()
    conn = sqlite3.connect(DATABASE_PATH)
    registros = conn.execute(
        """
        SELECT data_hora, acao, detalhe
        FROM auditoria
        ORDER BY datetime(data_hora) DESC
        LIMIT ?
        """,
        (limite,)
    ).fetchall()
    conn.close()
    timeline = []
    for data_hora, acao, detalhe in registros:
        try:
            momento = datetime.fromisoformat(data_hora)
        except (TypeError, ValueError):
            momento = datetime.now()
        timeline.append({
            "hora": momento.strftime("%H:%M"),
            "data": momento.strftime("%d/%m"),
            "acao": acao,
            "detalhe": detalhe or "Ação registrada no sistema",
            "tipo": (
                "success" if "Importou" in acao
                else "purple" if "PDF" in acao
                else "warning" if "bloqueio" in acao.lower()
                else "blue"
            )
        })
    return timeline


def obter_inteligencia_sistema():
    agora = datetime.now()
    hoje = agora.date()
    amanha = hoje + timedelta(days=1)
    colaboradores = obter_colaboradores()
    periodos = [
        {**periodo, "nome": colaborador["nome"],
         "departamento": colaborador["departamento"]}
        for colaborador in colaboradores
        for periodo in colaborador["periodos"]
    ]
    quem_sai = sorted(
        [item for item in periodos if hoje <= item["inicio"] <= hoje + timedelta(days=7)],
        key=lambda item: item["inicio"]
    )
    quem_volta = sorted(
        [item for item in periodos if hoje <= item["fim"] <= hoje + timedelta(days=7)],
        key=lambda item: item["fim"]
    )

    inicializar_tabelas_sistema()
    conn = sqlite3.connect(DATABASE_PATH)
    bloqueios = conn.execute(
        "SELECT nome, data_bloqueio FROM bloqueios"
    ).fetchall() if conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='bloqueios'"
    ).fetchone() else []
    realizados = {(normalizar_texto(nome), data) for nome, data in bloqueios}
    pendentes = [
        item for item in periodos
        if item["bloqueio"] and item["bloqueio"] <= hoje
        and (
            normalizar_texto(item["nome"]),
            str(item["bloqueio"])
        ) not in realizados
    ]
    hoje_iso = hoje.isoformat()
    acoes_hoje = conn.execute(
        """
        SELECT acao, resultado FROM auditoria
        WHERE substr(data_hora, 1, 10) = ?
        """,
        (hoje_iso,)
    ).fetchall()
    conn.close()

    importacoes = sum(
        1 for acao, resultado in acoes_hoje
        if "Importou" in acao and resultado == "Sucesso"
    )
    erros = sum(1 for _, resultado in acoes_hoje if resultado == "Falha")
    bloqueios_hoje = sum(
        1 for item in periodos if item["bloqueio"] == hoje
    )
    ferias_amanha = sum(1 for item in periodos if item["inicio"] == amanha)
    retornos_hoje = sum(1 for item in periodos if item["fim"] == hoje)
    ferias_hoje = sum(
        1 for item in periodos if item["inicio"] <= hoje <= item["fim"]
    )

    departamentos = {}
    for colaborador in colaboradores:
        nome = colaborador["departamento"]
        departamentos[nome] = departamentos.get(nome, 0) + 1
    departamentos_lista = sorted(
        departamentos.items(), key=lambda item: item[1], reverse=True
    )

    caminhos = planilhas_importadas()
    caminho = planilha_mais_recente()
    vendas = []
    if caminhos:
        try:
            df = carregar_planilhas(caminhos)
            coluna_venda = encontrar_coluna(
                df, ["abono", "venda ferias", "vendeu ferias", "dias vendidos"]
            )
            if coluna_venda:
                for _, linha in df.iterrows():
                    valor = str(linha.get(coluna_venda, "")).strip()
                    if valor and valor.lower() not in {"nan", "não", "nao", "0", "0.0"}:
                        vendas.append({
                            "nome": str(linha["Nome"]),
                            "valor": valor
                        })
        except (ValueError, OSError):
            pass

    total = len(colaboradores)
    em_ferias = sum(
        1 for item in colaboradores if item["status_classe"] == "active"
    )
    ocupacao = round((em_ferias / total) * 100) if total else 0
    devidos = sum(1 for item in periodos if item["bloqueio"] and item["bloqueio"] <= hoje)
    execucao = round(((devidos - len(pendentes)) / devidos) * 100) if devidos else 100
    alertas = [
        {
            "nivel": "danger", "icone": "lock-keyhole",
            "titulo": f"{bloqueios_hoje} bloqueio(s) hoje",
            "descricao": "Acessos programados para bloqueio.",
            "href": "/dashboard#alertas"
        },
        {
            "nivel": "warning", "icone": "calendar-clock",
            "titulo": f"{ferias_amanha} férias amanhã",
            "descricao": "Colaboradores com saída programada.",
            "href": "/calendario"
        },
        {
            "nivel": "info", "icone": "log-in",
            "titulo": f"{retornos_hoje} retorno(s) hoje",
            "descricao": "Colaboradores com retorno programado.",
            "href": "/calendario"
        },
        {
            "nivel": "success", "icone": "file-check-2",
            "titulo": "Importação realizada" if caminho else "Sem importação",
            "descricao": (
                datetime.fromtimestamp(os.path.getmtime(caminho)).strftime(
                    "Base atualizada em %d/%m às %H:%M."
                ) if caminho else "Nenhuma base disponível."
            ),
            "href": "/importar"
        },
        {
            "nivel": "info", "icone": "database-backup",
            "titulo": "Backup executado" if listar_backups() else "Backup pendente",
            "descricao": (
                datetime.fromtimestamp(os.path.getmtime(listar_backups()[0])).strftime(
                    "Última cópia em %d/%m às %H:%M."
                ) if listar_backups() else "Crie a primeira cópia de segurança."
            ),
            "href": "/configuracoes#backup"
        }
    ]
    return {
        "alertas": alertas,
        "operacoes": {
            "bloqueios": bloqueios_hoje,
            "retornos": retornos_hoje,
            "ferias": ferias_hoje,
            "importacoes": importacoes,
            "erros": erros
        },
        "executivo": {
            "funcionarios": total, "em_ferias": em_ferias,
            "ocupacao": ocupacao, "bloqueios": bloqueios_hoje,
            "execucao": max(0, execucao),
            "departamentos": departamentos_lista[:6]
        },
        "rh": {
            "quem_sai": quem_sai[:12],
            "quem_volta": quem_volta[:12],
            "vendas": vendas[:12],
            "atrasados": pendentes[:12],
            "pendentes": len(pendentes)
        },
        "ti": {
            "importacoes": importacoes,
            "logs": len(acoes_hoje),
            "backups": len(listar_backups()),
            "erros": erros,
            "saude": obter_saude_sistema()
        }
    }


def gerar_pdf_calendario(ferias, mes_nome, ano):
    preferencias = carregar_configuracoes()
    def pdf_texto(valor):
        texto = str(valor).encode("latin-1", "replace").decode("latin-1")
        return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    linhas_por_pagina = 23
    paginas = [ferias[i:i + linhas_por_pagina] for i in range(0, len(ferias), linhas_por_pagina)] or [[]]
    objetos = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    }
    referencias_paginas = []
    proximo_objeto = 5

    for indice, pagina in enumerate(paginas, start=1):
        pagina_id, conteudo_id = proximo_objeto, proximo_objeto + 1
        proximo_objeto += 2
        referencias_paginas.append(f"{pagina_id} 0 R")
        comandos = [
            "0.032 0.184 0.357 rg 0 772 595 70 re f",
            "BT /F2 19 Tf 1 1 1 rg 42 806 Td (Calendario de Ferias) Tj ET",
            f"BT /F1 10 Tf 0.82 0.9 1 rg 42 787 Td ({pdf_texto(mes_nome)} de {ano}) Tj ET",
            "0.93 0.96 0.99 rg 35 734 525 28 re f",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 42 744 Td (COLABORADOR) Tj ET",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 205 744 Td (SETOR) Tj ET",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 325 744 Td (INICIO) Tj ET",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 385 744 Td (FIM) Tj ET",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 445 744 Td (BLOQUEIO) Tj ET",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 510 744 Td (STATUS) Tj ET"
        ]
        if preferencias.get("pdf_logo") == "1":
            comandos.append("BT /F2 9 Tf 0.45 0.72 1 rg 500 806 Td (FOKUS) Tj ET")
        if preferencias.get("pdf_data") == "1":
            comandos.append(
                f"BT /F1 7 Tf 0.55 0.62 0.7 rg 430 787 Td (Gerado em {datetime.now():%d/%m/%Y}) Tj ET"
            )
        y = 715
        for linha, item in enumerate(pagina):
            if linha % 2:
                comandos.append(f"0.97 0.98 0.99 rg 35 {y - 8} 525 27 re f")
            comandos.extend([
                f"BT /F1 8 Tf 0.16 0.22 0.3 rg 42 {y} Td ({pdf_texto(item['nome'])[:34]}) Tj ET",
                f"BT /F1 8 Tf 0.3 0.37 0.46 rg 205 {y} Td ({pdf_texto(item['departamento'])[:22]}) Tj ET",
                f"BT /F1 8 Tf 0.3 0.37 0.46 rg 325 {y} Td ({item['inicio_formatado'][:5]}) Tj ET",
                f"BT /F1 8 Tf 0.3 0.37 0.46 rg 385 {y} Td ({item['fim_formatado'][:5]}) Tj ET",
                f"BT /F1 8 Tf 0.3 0.37 0.46 rg 445 {y} Td ({item['bloqueio_formatado'][:5]}) Tj ET",
                f"BT /F2 7 Tf 0.07 0.45 0.38 rg 510 {y} Td ({pdf_texto(item['status'])[:10]}) Tj ET"
            ])
            y -= 28
        if preferencias.get("pdf_rodape") == "1":
            comandos.append("BT /F1 8 Tf 0.45 0.5 0.58 rg 35 28 Td (Grupo Fokus Logistica - Sistema de Controle de Ferias) Tj ET")
        if preferencias.get("pdf_numero_pagina") == "1":
            comandos.append(f"BT /F1 8 Tf 0.45 0.5 0.58 rg 520 28 Td ({indice}/{len(paginas)}) Tj ET")
        stream = "\n".join(comandos).encode("latin-1")
        objetos[conteudo_id] = f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        objetos[pagina_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {conteudo_id} 0 R >>"
        ).encode("ascii")

    objetos[2] = f"<< /Type /Pages /Kids [{' '.join(referencias_paginas)}] /Count {len(referencias_paginas)} >>".encode("ascii")
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max(objetos) + 1)
    for numero in range(1, max(objetos) + 1):
        offsets[numero] = len(pdf)
        pdf.extend(f"{numero} 0 obj\n".encode("ascii"))
        pdf.extend(objetos[numero])
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii"))
    return bytes(pdf)


def obter_colaboradores():
    caminhos = planilhas_importadas()
    if not caminhos:
        return []

    try:
        df = carregar_planilhas(caminhos)
    except ValueError:
        return []

    coluna_departamento = encontrar_coluna(df, ["departamento", "depto / setor", "depto", "setor"])
    coluna_cargo = encontrar_coluna(df, ["cargo", "funcao"])
    coluna_matricula = encontrar_coluna(df, ["matricula"])
    coluna_filial = encontrar_coluna(df, ["filial", "unidade"])

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS colaborador_perfis (
            nome TEXT PRIMARY KEY,
            departamento TEXT,
            cargo TEXT,
            matricula TEXT,
            filial TEXT,
            atualizado_em TEXT
        )
    """)
    cursor.execute("SELECT nome, departamento, cargo, matricula, filial FROM colaborador_perfis")
    substituicoes = {
        normalizar_texto(nome): {
            "departamento": departamento,
            "cargo": cargo,
            "matricula": matricula,
            "filial": filial
        }
        for nome, departamento, cargo, matricula, filial in cursor.fetchall()
    }
    conn.close()

    def texto_valido(valor, padrao="Não informado"):
        if valor is None or pd.isna(valor) or str(valor).strip() in ("", "nan"):
            return padrao
        texto = str(valor).strip()
        if texto.endswith(".0") and texto[:-2].isdigit():
            return texto[:-2]
        return texto

    grupos = {}
    hoje = datetime.now().date()
    for _, linha in df.iterrows():
        nome = str(linha["Nome"]).strip()
        chave = normalizar_texto(nome)
        if chave not in grupos:
            grupos[chave] = {
                "nome": nome,
                "departamento": texto_valido(linha.get(coluna_departamento) if coluna_departamento else None),
                "cargo": texto_valido(linha.get(coluna_cargo) if coluna_cargo else None),
                "matricula": texto_valido(linha.get(coluna_matricula) if coluna_matricula else None, "-"),
                "filial": texto_valido(linha.get(coluna_filial) if coluna_filial else None),
                "periodos": []
            }

        inicio = linha["Inicio"].date() if pd.notna(linha["Inicio"]) else None
        fim = linha["Fim"].date() if pd.notna(linha["Fim"]) else None
        bloqueio = linha["Data de Bloqueio"].date() if pd.notna(linha["Data de Bloqueio"]) else None
        if inicio and fim:
            grupos[chave]["periodos"].append({
                "inicio": inicio,
                "fim": fim,
                "bloqueio": bloqueio,
                "inicio_formatado": inicio.strftime("%d/%m/%Y"),
                "fim_formatado": fim.strftime("%d/%m/%Y"),
                "bloqueio_formatado": bloqueio.strftime("%d/%m/%Y") if bloqueio else "-"
            })

    colaboradores = []
    for chave, colaborador in grupos.items():
        perfil = substituicoes.get(chave, {})
        for campo in ["departamento", "cargo", "matricula", "filial"]:
            if perfil.get(campo):
                colaborador[campo] = perfil[campo]

        periodos = sorted(colaborador["periodos"], key=lambda item: item["inicio"])
        ativos = [item for item in periodos if item["inicio"] <= hoje <= item["fim"]]
        futuros = [item for item in periodos if item["inicio"] > hoje]
        passados = [item for item in periodos if item["fim"] < hoje]

        if ativos:
            periodo_atual = ativos[0]
            status, status_classe = "Em férias", "active"
        elif futuros:
            periodo_atual = futuros[0]
            status, status_classe = "Programada", "scheduled"
        elif passados:
            periodo_atual = passados[-1]
            status, status_classe = "Concluída", "completed"
        else:
            periodo_atual = None
            status, status_classe = "Sem período", "neutral"

        colaborador.update({
            "periodos": periodos,
            "periodo_atual": periodo_atual,
            "status": status,
            "status_classe": status_classe,
            "slug": quote(colaborador["nome"], safe=""),
            "iniciais": "".join(parte[0] for parte in colaborador["nome"].split()[:2]).upper(),
            "cor": sum(ord(letra) for letra in colaborador["nome"]) % 4
        })
        colaboradores.append(colaborador)

    return sorted(colaboradores, key=lambda item: normalizar_texto(item["nome"]))


def obter_historico():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bloqueios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT,
            data_bloqueio TEXT,
            data_execucao TEXT
        )
    """)

    cursor.execute("""
        SELECT nome, data_bloqueio, data_execucao
        FROM bloqueios
        ORDER BY datetime(data_execucao) DESC
    """)
    registros = cursor.fetchall()
    conn.close()

    dados = []
    for nome, data_bloqueio, data_execucao in registros:
        try:
            bloqueio_dt = datetime.fromisoformat(str(data_bloqueio))
        except (TypeError, ValueError):
            bloqueio_dt = None

        try:
            execucao_dt = datetime.fromisoformat(str(data_execucao))
        except (TypeError, ValueError):
            execucao_dt = None

        dados.append({
            "nome": nome,
            "data_bloqueio": bloqueio_dt.strftime("%d/%m/%Y") if bloqueio_dt else str(data_bloqueio or "-"),
            "data_execucao": execucao_dt.strftime("%d/%m/%Y %H:%M") if execucao_dt else str(data_execucao or "-"),
            "execucao_hora": execucao_dt.strftime("%H:%M") if execucao_dt else "--:--",
            "execucao_data_curta": execucao_dt.strftime("%d/%m") if execucao_dt else "--/--",
            "execucao_dt": execucao_dt,
            "status": "Executado"
        })

    return dados


def gerar_pdf_historico(dados):
    preferencias = carregar_configuracoes()
    def pdf_texto(valor):
        texto = str(valor).encode("latin-1", "replace").decode("latin-1")
        return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    linhas_por_pagina = 24
    paginas = [dados[i:i + linhas_por_pagina] for i in range(0, len(dados), linhas_por_pagina)] or [[]]
    objetos = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    }
    referencias_paginas = []
    proximo_objeto = 5

    for indice, pagina in enumerate(paginas, start=1):
        pagina_id = proximo_objeto
        conteudo_id = proximo_objeto + 1
        proximo_objeto += 2
        referencias_paginas.append(f"{pagina_id} 0 R")

        subtitulo = (
            f"Gerado em {datetime.now():%d/%m/%Y %H:%M}"
            if preferencias.get("pdf_data") == "1" else ""
        )
        comandos = [
            "0.032 0.184 0.357 rg 0 772 595 70 re f",
            "BT /F2 19 Tf 1 1 1 rg 42 806 Td (Historico de Bloqueios) Tj ET",
            f"BT /F1 9 Tf 0.82 0.9 1 rg 42 787 Td ({subtitulo}) Tj ET",
            "0.93 0.96 0.99 rg 42 736 511 25 re f",
            "BT /F2 9 Tf 0.18 0.25 0.34 rg 49 745 Td (COLABORADOR) Tj ET",
            "BT /F2 9 Tf 0.18 0.25 0.34 rg 250 745 Td (BLOQUEIO) Tj ET",
            "BT /F2 9 Tf 0.18 0.25 0.34 rg 350 745 Td (EXECUTADO EM) Tj ET",
            "BT /F2 9 Tf 0.18 0.25 0.34 rg 488 745 Td (STATUS) Tj ET"
        ]
        if preferencias.get("pdf_logo") == "1":
            comandos.append("BT /F2 9 Tf 0.45 0.72 1 rg 500 806 Td (FOKUS) Tj ET")

        y = 718
        for linha, item in enumerate(pagina):
            if linha % 2:
                comandos.append(f"0.97 0.98 0.99 rg 42 {y - 7} 511 25 re f")
            comandos.extend([
                f"BT /F1 9 Tf 0.16 0.22 0.3 rg 49 {y} Td ({pdf_texto(item['nome'])[:38]}) Tj ET",
                f"BT /F1 9 Tf 0.3 0.37 0.46 rg 250 {y} Td ({pdf_texto(item['data_bloqueio'])}) Tj ET",
                f"BT /F1 9 Tf 0.3 0.37 0.46 rg 350 {y} Td ({pdf_texto(item['data_execucao'])}) Tj ET",
                f"BT /F2 9 Tf 0.07 0.55 0.34 rg 488 {y} Td ({pdf_texto(item['status'])}) Tj ET"
            ])
            y -= 27

        if preferencias.get("pdf_rodape") == "1":
            comandos.append("BT /F1 8 Tf 0.45 0.5 0.58 rg 42 28 Td (Grupo Fokus Logistica - Sistema de Controle de Ferias) Tj ET")
        if preferencias.get("pdf_numero_pagina") == "1":
            comandos.append(f"BT /F1 8 Tf 0.45 0.5 0.58 rg 520 28 Td ({indice}/{len(paginas)}) Tj ET")
        stream = "\n".join(comandos).encode("latin-1")
        objetos[conteudo_id] = f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream"
        objetos[pagina_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {conteudo_id} 0 R >>"
        ).encode("ascii")

    objetos[2] = (
        f"<< /Type /Pages /Kids [{' '.join(referencias_paginas)}] /Count {len(referencias_paginas)} >>"
    ).encode("ascii")

    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max(objetos) + 1)
    for numero in range(1, max(objetos) + 1):
        offsets[numero] = len(pdf)
        pdf.extend(f"{numero} 0 obj\n".encode("ascii"))
        pdf.extend(objetos[numero])
        pdf.extend(b"\nendobj\n")

    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode("ascii")
    )
    return bytes(pdf)


def linhas_exportacao_relatorios(dados):
    return [
        [
            item["nome"],
            item["departamento"],
            item["inicio"].strftime("%d/%m/%Y"),
            item["fim"].strftime("%d/%m/%Y"),
            item["bloqueio"].strftime("%d/%m/%Y") if item["bloqueio"] else "-",
            item["dias"],
            item["status"]
        ]
        for item in dados["registros"]
    ]


def gerar_pdf_relatorios(dados):
    preferencias = carregar_configuracoes()
    def texto_pdf(valor):
        texto = str(valor).encode("latin-1", "replace").decode("latin-1")
        return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    linhas = linhas_exportacao_relatorios(dados)
    paginas = [linhas[i:i + 24] for i in range(0, len(linhas), 24)] or [[]]
    objetos = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"
    }
    referencias = []
    proximo = 5

    for indice, pagina in enumerate(paginas, start=1):
        pagina_id, conteudo_id = proximo, proximo + 1
        proximo += 2
        referencias.append(f"{pagina_id} 0 R")
        comandos = [
            "0.032 0.184 0.357 rg 0 772 595 70 re f",
            "BT /F2 19 Tf 1 1 1 rg 42 806 Td (Relatorio Executivo de Ferias) Tj ET",
            f"BT /F1 9 Tf 0.82 0.9 1 rg 42 787 Td ({texto_pdf(dados['periodo_nome'])}) Tj ET",
            "0.93 0.96 0.99 rg 35 736 525 25 re f",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 41 745 Td (COLABORADOR) Tj ET",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 215 745 Td (DEPARTAMENTO) Tj ET",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 335 745 Td (INICIO) Tj ET",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 404 745 Td (FIM) Tj ET",
            "BT /F2 8 Tf 0.18 0.25 0.34 rg 471 745 Td (STATUS) Tj ET"
        ]
        if preferencias.get("pdf_logo") == "1":
            comandos.append("BT /F2 9 Tf 0.45 0.72 1 rg 500 806 Td (FOKUS) Tj ET")
        if preferencias.get("pdf_data") == "1":
            comandos.append(
                f"BT /F1 7 Tf 0.55 0.62 0.7 rg 430 787 Td (Gerado em {datetime.now():%d/%m/%Y}) Tj ET"
            )
        y = 718
        for linha_indice, linha in enumerate(pagina):
            if linha_indice % 2:
                comandos.append(f"0.97 0.98 0.99 rg 35 {y - 7} 525 25 re f")
            comandos.extend([
                f"BT /F1 8 Tf 0.16 0.22 0.3 rg 41 {y} Td ({texto_pdf(linha[0])[:38]}) Tj ET",
                f"BT /F1 8 Tf 0.3 0.37 0.46 rg 215 {y} Td ({texto_pdf(linha[1])[:25]}) Tj ET",
                f"BT /F1 8 Tf 0.3 0.37 0.46 rg 335 {y} Td ({texto_pdf(linha[2])}) Tj ET",
                f"BT /F1 8 Tf 0.3 0.37 0.46 rg 404 {y} Td ({texto_pdf(linha[3])}) Tj ET",
                f"BT /F2 8 Tf 0.07 0.45 0.34 rg 471 {y} Td ({texto_pdf(linha[6])[:18]}) Tj ET"
            ])
            y -= 27
        if preferencias.get("pdf_rodape") == "1":
            comandos.append("BT /F1 8 Tf 0.45 0.5 0.58 rg 35 28 Td (Grupo Fokus Logistica - Sistema de Controle de Ferias) Tj ET")
        if preferencias.get("pdf_numero_pagina") == "1":
            comandos.append(f"BT /F1 8 Tf 0.45 0.5 0.58 rg 520 28 Td ({indice}/{len(paginas)}) Tj ET")
        stream = "\n".join(comandos).encode("latin-1")
        objetos[conteudo_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream + b"\nendstream"
        )
        objetos[pagina_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
            f"/Contents {conteudo_id} 0 R >>"
        ).encode("ascii")

    objetos[2] = (
        f"<< /Type /Pages /Kids [{' '.join(referencias)}] /Count {len(referencias)} >>"
    ).encode("ascii")
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0] * (max(objetos) + 1)
    for numero in range(1, max(objetos) + 1):
        offsets[numero] = len(pdf)
        pdf.extend(f"{numero} 0 obj\n".encode("ascii"))
        pdf.extend(objetos[numero])
        pdf.extend(b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF".encode("ascii")
    )
    return bytes(pdf)
