from __future__ import annotations

import os

from services.column_mapper import ColumnMapper
from services.compare_service import CompareService
from services.file_reader import FileReader


class ImportComparator:
    """Compatibilidade para comparação por caminhos de arquivos."""

    def __init__(self):
        self.file_reader = FileReader()
        self.column_mapper = ColumnMapper()
        self.compare_service = CompareService()

    def compare(self, caminho_anterior: str | None, caminho_novo: str) -> dict:
        current = self.file_reader.read(caminho_novo)
        current_mapping = self.column_mapper.discover(
            current.columns
        )["colunas"]

        if not caminho_anterior or not os.path.exists(caminho_anterior):
            return self.compare_service.compare(
                None,
                current.dataframe,
                current_mapping=current_mapping
            )

        try:
            previous = self.file_reader.read(caminho_anterior)
            previous_mapping = self.column_mapper.discover(
                previous.columns
            )["colunas"]
            return self.compare_service.compare(
                previous.dataframe,
                current.dataframe,
                previous_mapping=previous_mapping,
                current_mapping=current_mapping
            )
        except (OSError, ValueError, ImportError):
            return self.compare_service.compare(
                None,
                current.dataframe,
                current_mapping=current_mapping
            )
