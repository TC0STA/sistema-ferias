from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from services.column_mapper import canonical_field, canonicalize_mapping
from services.import_utils import (
    converter_data,
    formatar_data,
    normalizar_texto,
    valor_vazio,
)


ROTULOS_COLUNAS = {
    "usuario": "Usuário",
    "data_inicio": "Data de Início",
    "data_fim": "Data de Fim",
    "nome": "Nome",
    "inicio": "Data Início",
    "fim": "Data Fim",
    "departamento": "Departamento",
    "matricula": "Matrícula",
}


@dataclass
class ImportValidationResult:
    arquivo: str
    total_registros: int
    validos: int
    invalidos: int
    pronta: bool
    erros: list[dict] = field(default_factory=list)
    avisos: list[dict] = field(default_factory=list)
    linhas: list[dict] = field(default_factory=list)
    previa: list[dict] = field(default_factory=list)
    validacao_arquivo: dict = field(default_factory=dict)
    mapeamento: dict = field(default_factory=dict)
    estrutura: dict = field(default_factory=dict)
    datas: dict = field(default_factory=dict)
    duplicidade: dict = field(default_factory=dict)
    campos_obrigatorios: dict = field(default_factory=dict)

    @classmethod
    def for_file_error(
        cls,
        filename: str,
        message: str,
        required_columns
    ):
        error = {
            "linha": 0,
            "campo": "Arquivo",
            "erro": message,
            "mensagem": message
        }
        return cls(
            arquivo=filename,
            total_registros=0,
            validos=0,
            invalidos=0,
            pronta=False,
            erros=[error],
            validacao_arquivo={"ok": False, "erro": message},
            estrutura={
                "ok": False,
                "colunas": [],
                "faltando": [
                    ROTULOS_COLUNAS[key] for key in required_columns
                ]
            },
            datas={"ok": False, "invalidas": 0, "periodos_invertidos": 0},
            duplicidade={
                "ok": False,
                "total": 0,
                "registros": 0,
                "matriculas": 0
            },
            campos_obrigatorios={
                "ok": False,
                "nomes_vazios": 0,
                "matriculas_vazias": 0,
                "departamentos_vazios": 0,
                "linhas_vazias": 0,
                "matricula_presente": False,
                "departamento_presente": False
            }
        )

    def to_dict(self) -> dict:
        resultado = asdict(self)
        status = "SUCESSO" if self.pronta else "ERRO"
        if self.mapeamento.get("requer_confirmacao"):
            status = "MAPEAMENTO_NECESSARIO"
        resultado.update({
            "status": status,
            "total": self.total_registros,
            "registros": self.total_registros,
            "registros_validos": self.validos,
            "total_erros": len(self.erros)
        })
        return resultado


class ImportValidator:
    """Valida uma planilha linha por linha e devolve um resultado completo."""

    def __init__(
        self,
        *,
        colunas_obrigatorias=("usuario", "data_inicio", "data_fim")
    ):
        canonical = tuple(
            canonical_field(field) for field in colunas_obrigatorias
        )
        desconhecidas = set(canonical) - {
            "usuario", "data_inicio", "data_fim",
            "matricula", "departamento",
        }
        if desconhecidas:
            raise ValueError(
                "Coluna(s) obrigatória(s) desconhecida(s): "
                f"{', '.join(sorted(desconhecidas))}."
            )
        self.colunas_obrigatorias = canonical

    def validate_dataframe(
        self,
        dataframe: pd.DataFrame,
        *,
        filename: str,
        header_row: int,
        mapping: dict,
        file_info: dict | None = None
    ) -> ImportValidationResult:
        """Valida somente conteúdo já lido e previamente mapeado."""
        df_bruto = dataframe
        linha_cabecalho = header_row
        mapeamento = {
            **mapping,
            "colunas": canonicalize_mapping(mapping.get("colunas")),
            "faltando": [
                {
                    **item,
                    "campo": canonical_field(item["campo"]),
                }
                for item in mapping.get("faltando", [])
            ],
            "ambiguidades": [
                {
                    **item,
                    "campo": canonical_field(item["campo"]),
                }
                for item in mapping.get("ambiguidades", [])
            ],
        }
        colunas = mapeamento["colunas"]
        df = df_bruto.reset_index(drop=True)
        if df.empty:
            return ImportValidationResult.for_file_error(
                filename,
                "A planilha não contém registros para importação.",
                self.colunas_obrigatorias
            )

        faltando = [
            item["rotulo"] for item in mapeamento["faltando"]
        ]
        ambiguidades = mapeamento["ambiguidades"]
        erros: list[dict] = []
        linhas: list[dict] = []
        previa: list[dict] = []
        contadores = {
            "nomes_vazios": 0,
            "matriculas_vazias": 0,
            "departamentos_vazios": 0,
            "linhas_vazias": 0,
            "datas_invalidas": 0,
            "periodos_invertidos": 0,
            "duplicados": 0,
            "matriculas_duplicadas": 0
        }
        chaves_vistas: dict[tuple[str, str, str], int] = {}
        matriculas_vistas: dict[str, int] = {}

        for rotulo in faltando:
            mensagem = (
                "Não encontrei uma coluna correspondente a "
                f"{rotulo}."
            )
            erros.append({
                "linha": linha_cabecalho + 1,
                "campo": "Estrutura",
                "erro": mensagem,
                "mensagem": mensagem
            })
        for ambiguidade in ambiguidades:
            erros.append({
                "linha": linha_cabecalho + 1,
                "campo": ambiguidade["rotulo"],
                "erro": ambiguidade["mensagem"],
                "mensagem": ambiguidade["mensagem"],
                "opcoes": ambiguidade["opcoes"]
            })

        if not faltando and not ambiguidades:
            for posicao, (_, linha) in enumerate(df.iterrows()):
                numero_linha = linha_cabecalho + posicao + 2
                erros_linha: list[dict] = []

                def adicionar_erro(campo, mensagem):
                    item = {
                        "linha": numero_linha,
                        "campo": campo,
                        "erro": mensagem,
                        "mensagem": mensagem
                    }
                    erros.append(item)
                    erros_linha.append(item)

                if all(valor_vazio(valor) for valor in linha.tolist()):
                    contadores["linhas_vazias"] += 1
                    adicionar_erro(
                        "Linha",
                        "Linha vazia sem dados para importação."
                    )
                    linhas.append({
                        "linha": numero_linha,
                        "status": "ERRO",
                        "erros": [{
                            "campo": "Linha",
                            "erro": "Linha vazia sem dados para importação."
                        }]
                    })
                    continue

                nome = linha.get(colunas["usuario"])
                inicio = converter_data(linha.get(colunas["data_inicio"]))
                fim = converter_data(linha.get(colunas["data_fim"]))
                matricula = (
                    linha.get(colunas["matricula"])
                    if colunas.get("matricula") is not None else None
                )
                departamento = (
                    linha.get(colunas["departamento"])
                    if colunas.get("departamento") is not None else None
                )

                if valor_vazio(nome):
                    contadores["nomes_vazios"] += 1
                    adicionar_erro("Nome", "Nome obrigatório não informado.")
                if (
                    colunas.get("matricula") is not None
                    and valor_vazio(matricula)
                ):
                    contadores["matriculas_vazias"] += 1
                    adicionar_erro("Matrícula", "Matrícula não informada.")
                if (
                    colunas.get("departamento") is not None
                    and valor_vazio(departamento)
                ):
                    contadores["departamentos_vazios"] += 1
                    adicionar_erro(
                        "Departamento",
                        "Departamento não informado."
                    )
                if (
                    colunas.get("matricula") is not None
                    and not valor_vazio(matricula)
                ):
                    chave_matricula = normalizar_texto(matricula)
                    if chave_matricula in matriculas_vistas:
                        contadores["matriculas_duplicadas"] += 1
                        adicionar_erro(
                            "Matrícula",
                            (
                                "Matrícula duplicada da linha "
                                f"{matriculas_vistas[chave_matricula]}."
                            )
                        )
                    else:
                        matriculas_vistas[chave_matricula] = numero_linha
                if pd.isna(inicio):
                    contadores["datas_invalidas"] += 1
                    adicionar_erro(
                        "Data Início",
                        "Data inicial vazia ou inválida."
                    )
                if pd.isna(fim):
                    contadores["datas_invalidas"] += 1
                    adicionar_erro(
                        "Data Fim",
                        "Data final vazia ou inválida."
                    )
                if (
                    not pd.isna(inicio)
                    and not pd.isna(fim)
                    and inicio > fim
                ):
                    contadores["periodos_invertidos"] += 1
                    adicionar_erro(
                        "Período",
                        "A data inicial é posterior à data final."
                    )

                if (
                    not valor_vazio(nome)
                    and not pd.isna(inicio)
                    and not pd.isna(fim)
                ):
                    chave = (
                        normalizar_texto(nome),
                        pd.Timestamp(inicio).date().isoformat(),
                        pd.Timestamp(fim).date().isoformat()
                    )
                    if chave in chaves_vistas:
                        contadores["duplicados"] += 1
                        adicionar_erro(
                            "Duplicidade",
                            (
                                "Registro duplicado da linha "
                                f"{chaves_vistas[chave]}."
                            )
                        )
                    else:
                        chaves_vistas[chave] = numero_linha

                linhas.append({
                    "linha": numero_linha,
                    "status": "ERRO" if erros_linha else "OK",
                    "erros": [
                        {"campo": item["campo"], "erro": item["erro"]}
                        for item in erros_linha
                    ]
                })
                if not erros_linha:
                    previa.append({
                        "nome": str(nome).strip(),
                        "matricula": (
                            "" if colunas.get("matricula") is None
                            else str(matricula).strip()
                        ),
                        "departamento": (
                            "" if colunas.get("departamento") is None
                            else str(departamento).strip()
                        ),
                        "inicio": formatar_data(inicio),
                        "fim": formatar_data(fim)
                    })

        estrutura_ok = not faltando and not ambiguidades
        datas_ok = (
            contadores["datas_invalidas"] == 0
            and contadores["periodos_invertidos"] == 0
        )
        campos_ok = (
            contadores["nomes_vazios"] == 0
            and contadores["matriculas_vazias"] == 0
            and contadores["departamentos_vazios"] == 0
            and contadores["linhas_vazias"] == 0
        )
        pronta = (
            estrutura_ok
            and datas_ok
            and campos_ok
            and contadores["duplicados"] == 0
            and contadores["matriculas_duplicadas"] == 0
        )
        invalidos = sum(1 for linha in linhas if linha["status"] == "ERRO")
        if faltando or ambiguidades:
            invalidos = len(df)

        return ImportValidationResult(
            arquivo=filename,
            total_registros=len(df),
            validos=max(0, len(df) - invalidos),
            invalidos=invalidos,
            pronta=pronta,
            erros=erros,
            linhas=linhas,
            previa=previa[:5],
            validacao_arquivo=file_info or {"ok": True},
            mapeamento=mapeamento,
            estrutura={
                "ok": estrutura_ok,
                "colunas": [str(coluna) for coluna in df.columns],
                "faltando": faltando
            },
            datas={
                "ok": datas_ok,
                "invalidas": contadores["datas_invalidas"],
                "periodos_invertidos": contadores["periodos_invertidos"]
            },
            duplicidade={
                "ok": (
                    contadores["duplicados"] == 0
                    and contadores["matriculas_duplicadas"] == 0
                ),
                "total": (
                    contadores["duplicados"]
                    + contadores["matriculas_duplicadas"]
                ),
                "registros": contadores["duplicados"],
                "matriculas": contadores["matriculas_duplicadas"]
            },
            campos_obrigatorios={
                "ok": campos_ok,
                "nomes_vazios": contadores["nomes_vazios"],
                "matriculas_vazias": contadores["matriculas_vazias"],
                "departamentos_vazios": contadores[
                    "departamentos_vazios"
                ],
                "linhas_vazias": contadores["linhas_vazias"],
                "matricula_presente": colunas.get("matricula") is not None,
                "departamento_presente": (
                    colunas.get("departamento") is not None
                )
            }
        )
