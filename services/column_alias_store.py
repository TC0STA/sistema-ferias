from __future__ import annotations

import sqlite3
from datetime import datetime

from services.column_mapper import FIELD_LABELS, canonical_field
from services.import_utils import normalizar_texto


class ColumnAliasStore:
    """Aliases de cabeçalhos administráveis sem alteração de código."""

    def __init__(self, database_path: str):
        self.database_path = database_path

    def ensure_schema(self) -> None:
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS column_aliases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alias TEXT NOT NULL,
                    alias_normalizado TEXT NOT NULL,
                    campo TEXT NOT NULL,
                    ativo INTEGER NOT NULL DEFAULT 1,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL,
                    UNIQUE(alias_normalizado, campo)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_column_aliases_campo_ativo
                ON column_aliases (campo, ativo)
            """)
            connection.commit()
        finally:
            connection.close()

    def save(self, alias: str, field: str) -> dict:
        canonical = canonical_field(str(field))
        if canonical not in FIELD_LABELS:
            raise ValueError(f"Campo de alias desconhecido: {field}.")
        visible_alias = str(alias).strip()
        normalized_alias = normalizar_texto(visible_alias)
        if not normalized_alias:
            raise ValueError("O alias não pode ser vazio.")

        self.ensure_schema()
        now = datetime.now().isoformat(timespec="seconds")
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO column_aliases (
                    alias, alias_normalizado, campo, ativo,
                    criado_em, atualizado_em
                ) VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(alias_normalizado, campo) DO UPDATE SET
                    alias = excluded.alias,
                    ativo = 1,
                    atualizado_em = excluded.atualizado_em
                """,
                (visible_alias, normalized_alias, canonical, now, now),
            )
            row = connection.execute(
                """
                SELECT id, alias, campo, ativo, criado_em, atualizado_em
                FROM column_aliases
                WHERE alias_normalizado = ? AND campo = ?
                """,
                (normalized_alias, canonical),
            ).fetchone()
            connection.commit()
        finally:
            connection.close()
        return self._row(row)

    def list(self, *, active_only: bool = True) -> list[dict]:
        self.ensure_schema()
        query = """
            SELECT id, alias, campo, ativo, criado_em, atualizado_em
            FROM column_aliases
        """
        if active_only:
            query += " WHERE ativo = 1"
        query += " ORDER BY campo, alias_normalizado"
        connection = sqlite3.connect(self.database_path)
        try:
            return [self._row(row) for row in connection.execute(query)]
        finally:
            connection.close()

    def as_mapping(self) -> dict[str, list[str]]:
        result = {field: [] for field in FIELD_LABELS}
        for item in self.list():
            result[item["campo"]].append(item["alias"])
        return result

    def deactivate(self, alias_id: int) -> bool:
        self.ensure_schema()
        now = datetime.now().isoformat(timespec="seconds")
        connection = sqlite3.connect(self.database_path)
        try:
            cursor = connection.execute(
                """
                UPDATE column_aliases
                SET ativo = 0, atualizado_em = ?
                WHERE id = ? AND ativo = 1
                """,
                (now, alias_id),
            )
            connection.commit()
            return cursor.rowcount > 0
        finally:
            connection.close()

    @staticmethod
    def _row(row) -> dict:
        return {
            "id": row[0],
            "alias": row[1],
            "campo": row[2],
            "ativo": bool(row[3]),
            "criado_em": row[4],
            "atualizado_em": row[5],
        }
