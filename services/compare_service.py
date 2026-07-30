from __future__ import annotations

import pandas as pd

from services.import_utils import mapa_colaboradores


class CompareService:
    """Compara dois DataFrames já lidos e mapeados."""

    def compare(
        self,
        previous: pd.DataFrame | None,
        current: pd.DataFrame,
        *,
        previous_mapping: dict | None = None,
        current_mapping: dict
    ) -> dict:
        current_users = mapa_colaboradores(current, current_mapping)
        if previous is None or not previous_mapping:
            return {
                "novos": len(current_users),
                "removidos": 0,
                "alterados": 0,
                "iguais": 0
            }

        previous_users = mapa_colaboradores(previous, previous_mapping)
        current_names = set(current_users)
        previous_names = set(previous_users)
        common = current_names & previous_names
        return {
            "novos": len(current_names - previous_names),
            "removidos": len(previous_names - current_names),
            "alterados": sum(
                1
                for name in common
                if current_users[name] != previous_users[name]
            ),
            "iguais": sum(
                1
                for name in common
                if current_users[name] == previous_users[name]
            )
        }
