from __future__ import annotations

import sqlite3
from datetime import datetime


class DashboardUpdater:
    """Invalida consumidores após a importação, sem conhecer suas telas."""

    MODULES = (
        "dashboard",
        "calendario",
        "historico",
        "centro_operacoes",
    )

    def __init__(self, database_path: str):
        self.database_path = database_path

    def ensure_schema(self):
        conn = sqlite3.connect(self.database_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS atualizacoes_modulos (
                    modulo TEXT PRIMARY KEY,
                    versao_importacao INTEGER NOT NULL,
                    atualizado_em TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def update_all(self, import_version: int) -> list[dict]:
        self.ensure_schema()
        updated_at = datetime.now().isoformat(timespec="seconds")
        conn = sqlite3.connect(self.database_path)
        try:
            for module in self.MODULES:
                conn.execute(
                    """
                    INSERT INTO atualizacoes_modulos (
                        modulo, versao_importacao, atualizado_em
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(modulo) DO UPDATE SET
                        versao_importacao = excluded.versao_importacao,
                        atualizado_em = excluded.atualizado_em
                    """,
                    (module, import_version, updated_at)
                )
            conn.commit()
        finally:
            conn.close()
        return [
            {
                "modulo": module,
                "versao_importacao": import_version,
                "atualizado_em": updated_at
            }
            for module in self.MODULES
        ]

    def status(self) -> list[dict]:
        self.ensure_schema()
        conn = sqlite3.connect(self.database_path)
        try:
            rows = conn.execute(
                """
                SELECT modulo, versao_importacao, atualizado_em
                FROM atualizacoes_modulos ORDER BY modulo
                """
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "modulo": row[0],
                "versao_importacao": row[1],
                "atualizado_em": row[2]
            }
            for row in rows
        ]
