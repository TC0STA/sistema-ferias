from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass

import pandas as pd

from services.import_utils import ler_planilha


class FileReadError(ValueError):
    pass


@dataclass(frozen=True)
class ExcelFileData:
    path: str
    filename: str
    extension: str
    size_bytes: int
    header_row: int
    dataframe: pd.DataFrame

    @property
    def columns(self) -> list[str]:
        return [str(column).strip() for column in self.dataframe.columns]


class FileReader:
    """Lê Excel e devolve dados; não valida, compara, persiste ou audita."""

    def __init__(self, allowed_extensions=(".xlsx", ".xls")):
        self.allowed_extensions = tuple(
            extension.lower() for extension in allowed_extensions
        )

    def read(self, path: str) -> ExcelFileData:
        if not os.path.isfile(path):
            raise FileReadError("Arquivo não encontrado.")
        extension = os.path.splitext(path)[1].lower()
        if extension not in self.allowed_extensions:
            allowed = ", ".join(self.allowed_extensions)
            raise FileReadError(
                f"Formato inválido. Extensões permitidas: {allowed}."
            )
        if os.path.getsize(path) == 0:
            raise FileReadError("O arquivo está vazio.")
        if extension == ".xlsx" and not zipfile.is_zipfile(path):
            raise FileReadError(
                "O arquivo Excel está corrompido ou possui formato inválido."
            )
        try:
            dataframe, header_row = ler_planilha(path)
        except Exception as error:
            raise FileReadError(
                "Não foi possível ler o arquivo Excel. "
                "O arquivo pode estar vazio ou corrompido."
            ) from error
        return ExcelFileData(
            path=path,
            filename=os.path.basename(path),
            extension=extension,
            size_bytes=os.path.getsize(path),
            header_row=header_row,
            dataframe=dataframe
        )
