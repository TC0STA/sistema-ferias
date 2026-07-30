from __future__ import annotations

import pandas as pd

from services.column_mapper import FIELD_LABELS, canonicalize_mapping
from services.import_utils import converter_data, normalizar_texto, valor_vazio


class ImportPreview:
    """Calcula o resumo da importação sem acessar arquivo ou banco de dados."""

    def build(
        self,
        dataframe: pd.DataFrame,
        *,
        mapping: dict,
        validation: dict
    ) -> dict:
        columns = canonicalize_mapping(mapping.get("colunas"))
        user_column = columns.get("usuario")
        start_column = columns.get("data_inicio")
        end_column = columns.get("data_fim")
        department_column = columns.get("departamento")

        users: set[str] = set()
        departments: set[str] = set()
        starts: list[pd.Timestamp] = []
        ends: list[pd.Timestamp] = []

        for _, row in dataframe.iterrows():
            if user_column:
                user = row.get(user_column)
                if not valor_vazio(user):
                    users.add(normalizar_texto(user))
            if department_column:
                department = row.get(department_column)
                if not valor_vazio(department):
                    departments.add(normalizar_texto(department))
            if start_column:
                start = converter_data(row.get(start_column))
                if not pd.isna(start):
                    starts.append(pd.Timestamp(start))
            if end_column:
                end = converter_data(row.get(end_column))
                if not pd.isna(end):
                    ends.append(pd.Timestamp(end))

        required = ("usuario", "data_inicio", "data_fim")
        identified_columns = [
            {
                "campo": field,
                "rotulo": FIELD_LABELS[field],
                "identificada": field in columns,
                "coluna": columns.get(field)
            }
            for field in required
        ]
        date_data = validation.get("datas", {})
        duplicate_data = validation.get("duplicidade", {})

        return {
            "registros_encontrados": len(dataframe),
            "usuarios_unicos": len(users),
            "departamentos": len(departments),
            "periodo": {
                "inicio": min(starts).strftime("%d/%m/%Y")
                if starts else None,
                "fim": max(ends).strftime("%d/%m/%Y")
                if ends else None
            },
            "datas_invalidas": (
                int(date_data.get("invalidas", 0))
                + int(date_data.get("periodos_invertidos", 0))
            ),
            "duplicados": int(duplicate_data.get("total", 0)),
            "colunas_identificadas": identified_columns
        }
