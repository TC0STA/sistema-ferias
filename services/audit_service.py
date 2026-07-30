from __future__ import annotations

import sqlite3
from datetime import datetime


class AuditService:
    """Registra auditoria sem depender de Flask, rotas ou interface."""

    def __init__(self, database_path: str):
        self.database_path = database_path

    def ensure_schema(self):
        conn = sqlite3.connect(self.database_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS auditoria (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hora TEXT NOT NULL,
                    acao TEXT NOT NULL,
                    detalhe TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    resultado TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def record(
        self,
        action: str,
        detail: str,
        *,
        user: str,
        ip: str,
        result: str = "Sucesso"
    ):
        self.ensure_schema()
        conn = sqlite3.connect(self.database_path)
        try:
            conn.execute(
                """
                INSERT INTO auditoria (
                    data_hora, acao, detalhe, usuario, ip, resultado
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.now().isoformat(timespec="seconds"),
                    action,
                    detail,
                    user,
                    ip,
                    result
                )
            )
            conn.commit()
        finally:
            conn.close()
