from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping

from services.import_utils import normalizar_texto


FIELD_LABELS = {
    "usuario": "Usuário",
    "data_inicio": "Data de Início",
    "data_fim": "Data de Fim",
    "matricula": "Matrícula",
    "departamento": "Departamento",
}

DEFAULT_ALIASES = {
    "usuario": (
        "usuario",
        "usuário",
        "nome",
        "colaborador",
        "funcionario",
        "funcionário",
        "nome do colaborador",
        "nome do funcionario",
        "nome do funcionário",
    ),
    "data_inicio": (
        "inicio",
        "início",
        "data inicio",
        "data início",
        "inicio das ferias",
        "início das férias",
        "inicio ferias",
        "ferias inicio",
        "férias início",
        "data inicial",
        "data de inicio",
        "data de início",
    ),
    "data_fim": (
        "fim",
        "retorno",
        "volta",
        "data fim",
        "data final",
        "data de fim",
        "data retorno",
        "fim das ferias",
        "fim das férias",
        "fim ferias",
    ),
    "matricula": (
        "matricula",
        "matrícula",
        "registro",
        "registro funcionario",
        "registro funcionário",
        "codigo funcionario",
        "código funcionário",
        "id funcionario",
        "id funcionário",
    ),
    "departamento": (
        "departamento",
        "depto",
        "depto setor",
        "setor",
        "area",
        "área",
        "lotacao",
        "lotação",
    ),
}

# Compatibilidade com integrações e perfis criados antes do padrão canônico.
LEGACY_TO_CANONICAL = {
    "nome": "usuario",
    "inicio": "data_inicio",
    "fim": "data_fim",
    "matricula": "matricula",
    "departamento": "departamento",
}
CANONICAL_TO_LEGACY = {
    canonical: legacy for legacy, canonical in LEGACY_TO_CANONICAL.items()
}

# Nomes públicos anteriores, mantidos para não quebrar extensões existentes.
ROTULOS = {
    CANONICAL_TO_LEGACY[field]: label
    for field, label in FIELD_LABELS.items()
}
SINONIMOS = {
    CANONICAL_TO_LEGACY[field]: aliases
    for field, aliases in DEFAULT_ALIASES.items()
}


def canonical_field(field: str) -> str:
    """Converte uma chave antiga para o padrão interno atual."""
    return LEGACY_TO_CANONICAL.get(field, field)


def canonicalize_mapping(mapping: Mapping | None) -> dict[str, str]:
    """Normaliza somente as chaves de um mapeamento, preservando as colunas."""
    if not mapping:
        return {}
    return {
        canonical_field(str(field)): column
        for field, column in mapping.items()
        if canonical_field(str(field)) in FIELD_LABELS
    }


def assinatura_colunas(colunas) -> str:
    normalizadas = [normalizar_texto(coluna) for coluna in colunas]
    conteudo = "\x1f".join(normalizadas).encode("utf-8")
    return hashlib.sha256(conteudo).hexdigest()


class ColumnMapper:
    """Associa cabeçalhos reais aos campos do padrão interno de importação."""

    def __init__(
        self,
        aliases: Mapping[str, Iterable[str]] | None = None,
        *,
        alias_store=None,
        sinonimos: Mapping[str, Iterable[str]] | None = None,
    ):
        # ``sinonimos`` é o nome legado do mesmo argumento.
        supplied = aliases if aliases is not None else sinonimos
        self._base_aliases = self._normalize_aliases(
            supplied or DEFAULT_ALIASES
        )
        self.alias_store = alias_store

    @staticmethod
    def _normalize_aliases(
        aliases: Mapping[str, Iterable[str]]
    ) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {
            field: [] for field in FIELD_LABELS
        }
        for field, values in aliases.items():
            canonical = canonical_field(str(field))
            if canonical not in result:
                raise ValueError(f"Campo de alias desconhecido: {field}.")
            for value in values:
                normalized = normalizar_texto(value)
                if normalized and normalized not in result[canonical]:
                    result[canonical].append(normalized)
        return {field: tuple(values) for field, values in result.items()}

    def _aliases(self) -> dict[str, tuple[str, ...]]:
        merged = {
            field: list(values)
            for field, values in self._base_aliases.items()
        }
        if self.alias_store is not None:
            stored = self.alias_store.as_mapping()
            for field, values in self._normalize_aliases(stored).items():
                for value in values:
                    if value not in merged[field]:
                        merged[field].append(value)
        return {field: tuple(values) for field, values in merged.items()}

    def map(
        self,
        headers,
        *,
        required=("usuario", "data_inicio", "data_fim"),
    ) -> dict[str, str]:
        """Retorna apenas ``campo canônico -> cabeçalho real``.

        Para diagnóstico de ausências e ambiguidades, use :meth:`discover`.
        """
        return self.discover(headers, obrigatorias=required)["colunas"]

    def discover(
        self,
        colunas,
        *,
        obrigatorias=("usuario", "data_inicio", "data_fim"),
        mapeamento_salvo: dict | None = None,
        mapeamento_confirmado: dict | None = None,
    ) -> dict:
        requested = tuple(str(field) for field in obrigatorias)
        required = tuple(canonical_field(field) for field in requested)
        unknown = set(required) - set(FIELD_LABELS)
        if unknown:
            raise ValueError(
                "Campo(s) obrigatório(s) desconhecido(s): "
                f"{', '.join(sorted(unknown))}."
            )

        # Chamadas explicitamente legadas continuam recebendo chaves legadas.
        legacy_output = bool(requested) and all(
            field in LEGACY_TO_CANONICAL for field in requested
        ) and any(field in {"nome", "inicio", "fim"} for field in requested)

        original_names = [str(column).strip() for column in colunas]
        by_normalized_name: dict[str, list[str]] = {}
        for original in original_names:
            by_normalized_name.setdefault(
                normalizar_texto(original), []
            ).append(original)

        source = "automático"
        predefined = None
        if mapeamento_confirmado:
            source = "confirmado"
            predefined = canonicalize_mapping(mapeamento_confirmado)
        elif mapeamento_salvo:
            source = "salvo"
            predefined = canonicalize_mapping(mapeamento_salvo)

        mapping: dict[str, str] = {}
        ambiguities: list[dict] = []
        missing: list[str] = []
        aliases = self._aliases()

        for field in FIELD_LABELS:
            if predefined and predefined.get(field) in original_names:
                mapping[field] = predefined[field]
                continue

            candidates: list[str] = []
            for alias in aliases.get(field, ()):
                candidates.extend(by_normalized_name.get(alias, []))
            candidates = list(dict.fromkeys(candidates))

            if len(candidates) == 1:
                mapping[field] = candidates[0]
            elif len(candidates) > 1:
                ambiguities.append({
                    "campo": field,
                    "rotulo": FIELD_LABELS[field],
                    "opcoes": candidates,
                    "mensagem": (
                        f"Encontrei {len(candidates)} colunas que podem "
                        f"representar {FIELD_LABELS[field]}. Escolha uma."
                    ),
                })
            elif field in required:
                missing.append(field)

        repeated: dict[str, list[str]] = {}
        for field, column in mapping.items():
            repeated.setdefault(column, []).append(field)
        for column, fields in repeated.items():
            if len(fields) <= 1:
                continue
            for field in fields:
                mapping.pop(field, None)
            ambiguities.append({
                "campo": fields[0],
                "rotulo": "Mapeamento",
                "opcoes": [column],
                "mensagem": (
                    f'A coluna “{column}” foi associada a mais de um campo. '
                    "Confirme o mapeamento."
                ),
            })

        for field in required:
            if (
                field not in mapping
                and field not in missing
                and not any(item["campo"] == field for item in ambiguities)
            ):
                missing.append(field)

        if legacy_output:
            output_mapping = {
                CANONICAL_TO_LEGACY[field]: column
                for field, column in mapping.items()
            }
            output_missing = [
                CANONICAL_TO_LEGACY[field] for field in missing
            ]
            output_ambiguities = [
                {
                    **item,
                    "campo": CANONICAL_TO_LEGACY[item["campo"]],
                }
                for item in ambiguities
            ]
        else:
            output_mapping = mapping
            output_missing = missing
            output_ambiguities = ambiguities

        return {
            "assinatura": assinatura_colunas(original_names),
            "origem": source,
            "colunas": output_mapping,
            "faltando": [
                {
                    "campo": (
                        CANONICAL_TO_LEGACY[field]
                        if legacy_output else field
                    ),
                    "rotulo": FIELD_LABELS[canonical_field(field)],
                }
                for field in output_missing
            ],
            "ambiguidades": output_ambiguities,
            "requer_confirmacao": bool(output_ambiguities),
            "completo": not output_missing and not output_ambiguities,
        }
