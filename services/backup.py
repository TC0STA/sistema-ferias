from __future__ import annotations

import os
import sqlite3
from datetime import datetime


class BackupService:
    """Cria cópias SQLite consistentes, hierárquicas e nunca sobrescritas."""

    def __init__(self, backups_root: str):
        self.backups_root = backups_root

    def before_import(self, database_path: str) -> str:
        if not os.path.isfile(database_path):
            raise FileNotFoundError(
                "O banco SQLite não foi encontrado para o backup obrigatório."
            )
        agora = datetime.now()
        pasta = os.path.join(
            self.backups_root,
            agora.strftime("%Y"),
            agora.strftime("%m"),
            agora.strftime("%d")
        )
        os.makedirs(pasta, exist_ok=True)
        nome = agora.strftime("backup_%H%M%S_%f.db")
        destino = os.path.join(pasta, nome)

        origem_conn = sqlite3.connect(database_path)
        destino_conn = sqlite3.connect(destino)
        try:
            origem_conn.backup(destino_conn)
        finally:
            destino_conn.close()
            origem_conn.close()
        return destino
