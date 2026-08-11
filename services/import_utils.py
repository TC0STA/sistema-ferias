from __future__ import annotations

import hashlib
import unicodedata
from datetime import date, datetime

import pandas as pd


COLUNAS = {
    "nome": [
        "nome", "funcionario", "colaborador", "usuario",
        "nome do colaborador", "nome do funcionario"
    ],
    "inicio": [
        "inicio", "inicio ferias", "inicio das ferias", "data inicio",
        "data de inicio", "ferias inicio", "data inicial"
    ],
    "fim": [
        "fim", "fim ferias", "fim das ferias", "data fim", "data de fim",
        "retorno", "data retorno", "volta", "data final"
    ],
    "departamento": [
        "departamento", "depto", "depto setor", "setor", "area", "lotacao"
    ],
    "matricula": [
        "matricula", "registro", "registro funcionario",
        "codigo funcionario", "id funcionario"
    ],
}


def normalizar_texto(valor) -> str:
    texto = str(valor).strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )


def valor_vazio(valor) -> bool:
    return pd.isna(valor) or str(valor).strip().lower() in {
        "", "nan", "nat", "none"
    }


def _merge_header_values(top: list, bottom: list) -> list[str]:
    merged = []
    for top_cell, bottom_cell in zip(top, bottom):
        top_text = "" if valor_vazio(top_cell) else str(top_cell).strip()
        bottom_text = "" if valor_vazio(bottom_cell) else str(bottom_cell).strip()
        if top_text and bottom_text:
            merged.append(f"{top_text} {bottom_text}".strip())
        elif top_text:
            merged.append(top_text)
        else:
            merged.append(bottom_text)
    return merged


def _header_candidate_values(values: list) -> list[str]:
    return [
        normalizar_texto(valor)
        for valor in values
        if not valor_vazio(valor)
    ]


def _is_header_row(values: list[str]) -> bool:
    tem_nome = any(valor in COLUNAS["nome"] for valor in values)
    tem_inicio = any(
        valor in COLUNAS["inicio"] or "inicio" in valor
        for valor in values
    )
    tem_fim = any(
        valor in COLUNAS["fim"] or "fim" in valor
        for valor in values
    )
    return tem_nome and tem_inicio and tem_fim


def _merge_multiindex_columns(columns):
    merged = []
    for coluna in columns:
        if isinstance(coluna, tuple):
            partes = [
                str(parte).strip()
                for parte in coluna
                if not valor_vazio(parte)
                and not str(parte).strip().startswith("Unnamed:")
            ]
            merged.append(" ".join(partes).strip())
        else:
            merged.append(str(coluna).strip())
    return merged


def encontrar_coluna(df: pd.DataFrame, opcoes: list[str]):
    normalizadas = [normalizar_texto(opcao) for opcao in opcoes]
    for coluna in df.columns:
        if normalizar_texto(coluna) in normalizadas:
            return coluna
    for coluna in df.columns:
        texto = normalizar_texto(coluna)
        if any(opcao in texto for opcao in normalizadas):
            return coluna
    return None


def _read_sheet_with_header(caminho: str, sheet_name) -> tuple[pd.DataFrame, int]:
    bruto = pd.read_excel(caminho, sheet_name=sheet_name, header=None, dtype=object)

    for indice in range(min(len(bruto), 30)):
        valores = _header_candidate_values(bruto.iloc[indice].tolist())

        if _is_header_row(valores):
            df = pd.read_excel(
                caminho,
                sheet_name=sheet_name,
                header=indice,
                dtype=object
            )
            df.columns = [str(coluna).strip() for coluna in df.columns]
            return df, indice

        if indice + 1 < len(bruto):
            combinados = _merge_header_values(
                bruto.iloc[indice].tolist(),
                bruto.iloc[indice + 1].tolist()
            )
            combinados_normalizados = _header_candidate_values(combinados)

            if _is_header_row(combinados_normalizados):
                df = pd.read_excel(
                    caminho,
                    sheet_name=sheet_name,
                    header=[indice, indice + 1],
                    dtype=object
                )
                df.columns = _merge_multiindex_columns(df.columns)
                df.columns = [str(coluna).strip() for coluna in df.columns]
                return df, indice

    df = pd.read_excel(caminho, sheet_name=sheet_name, dtype=object)
    df.columns = [str(coluna).strip() for coluna in df.columns]
    return df, 0


def ler_planilha(caminho: str) -> tuple[pd.DataFrame, int]:
    with pd.ExcelFile(caminho) as excel:
        nomes_planilhas = list(excel.sheet_names)
    resultados = []

    for sheet_name in nomes_planilhas:
        df, header_row = _read_sheet_with_header(caminho, sheet_name)
        if not df.empty:
            resultados.append((df, header_row))

    if not resultados:
        df = pd.read_excel(caminho, dtype=object)
        df.columns = [str(coluna).strip() for coluna in df.columns]
        return df, 0

    if len(resultados) == 1:
        return resultados[0]

    dataframes, header_rows = zip(*resultados)
    df = pd.concat(dataframes, ignore_index=True, sort=False)
    return df, 0


def filtrar_linhas_ativas(df: pd.DataFrame, colunas: dict):
    presentes = [coluna for coluna in colunas.values() if coluna is not None]
    if presentes:
        linhas_ativas = df[presentes].apply(
            lambda linha: any(not valor_vazio(valor) for valor in linha),
            axis=1
        )
        return df[linhas_ativas].copy().reset_index(drop=True)
    return df.dropna(how="all").copy().reset_index(drop=True)


def preparar_dados(caminho: str, mapeamento: dict | None = None):
    df, linha_cabecalho = ler_planilha(caminho)
    colunas = {
        chave: encontrar_coluna(df, opcoes)
        for chave, opcoes in COLUNAS.items()
    }
    for chave, coluna in (mapeamento or {}).items():
        if chave in colunas and coluna in df.columns:
            colunas[chave] = coluna
    return filtrar_linhas_ativas(df, colunas), linha_cabecalho, colunas


def converter_data(valor):
    if valor_vazio(valor):
        return pd.NaT
    if isinstance(valor, (pd.Timestamp, datetime, date)):
        return pd.Timestamp(valor)
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        try:
            return (
                pd.Timestamp("1899-12-30")
                + pd.to_timedelta(float(valor), unit="D")
            )
        except (ValueError, TypeError, OverflowError):
            return pd.NaT
    return pd.to_datetime(str(valor).strip(), errors="coerce", dayfirst=True)


def formatar_data(valor) -> str:
    if pd.isna(valor):
        return ""
    return pd.Timestamp(valor).strftime("%d/%m/%Y")


def mapa_colaboradores(
    df: pd.DataFrame,
    colunas: dict
) -> dict[str, set[tuple[str, str]]]:
    nome_coluna = colunas.get("usuario", colunas.get("nome"))
    inicio_coluna = colunas.get("data_inicio", colunas.get("inicio"))
    fim_coluna = colunas.get("data_fim", colunas.get("fim"))
    if any(
        coluna is None
        for coluna in (nome_coluna, inicio_coluna, fim_coluna)
    ):
        return {}
    mapa: dict[str, set[tuple[str, str]]] = {}
    for _, linha in df.iterrows():
        nome = linha.get(nome_coluna)
        inicio = converter_data(linha.get(inicio_coluna))
        fim = converter_data(linha.get(fim_coluna))
        if valor_vazio(nome) or pd.isna(inicio) or pd.isna(fim):
            continue
        chave = normalizar_texto(nome)
        mapa.setdefault(chave, set()).add((
            pd.Timestamp(inicio).date().isoformat(),
            pd.Timestamp(fim).date().isoformat()
        ))
    return mapa


def calcular_hash(caminho: str) -> str:
    digest = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()
