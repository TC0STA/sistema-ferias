from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime

from services.column_mapper import assinatura_colunas


class ImportProfileStore:
    """Mantém perfis reutilizáveis para diferentes layouts de planilha."""

    def __init__(self, database_path: str):
        self.database_path = database_path

    def ensure_schema(self):
        conn = sqlite3.connect(self.database_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS perfis_importacao (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    assinatura TEXT NOT NULL UNIQUE,
                    arquivo_referencia TEXT,
                    origem TEXT,
                    colunas_json TEXT NOT NULL,
                    mapeamento_json TEXT NOT NULL,
                    confirmado INTEGER NOT NULL DEFAULT 0,
                    ativo INTEGER NOT NULL DEFAULT 1,
                    utilizacoes INTEGER NOT NULL DEFAULT 0,
                    criado_em TEXT NOT NULL,
                    atualizado_em TEXT NOT NULL,
                    ultimo_uso_em TEXT
                )
            """)
            self._migrate_legacy(conn)
            conn.commit()
        finally:
            conn.close()

    def _migrate_legacy(self, conn):
        existe = conn.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'mapeamentos_colunas'
            """
        ).fetchone()
        if not existe:
            return
        agora = datetime.now().isoformat(timespec="seconds")
        linhas = conn.execute(
            """
            SELECT assinatura, colunas_json, mapeamento_json,
                   criado_em, atualizado_em
            FROM mapeamentos_colunas
            """
        ).fetchall()
        for assinatura, colunas, mapeamento, criado, atualizado in linhas:
            conn.execute(
                """
                INSERT OR IGNORE INTO perfis_importacao (
                    nome, assinatura, arquivo_referencia, origem,
                    colunas_json, mapeamento_json, confirmado, ativo,
                    utilizacoes, criado_em, atualizado_em
                ) VALUES (?, ?, NULL, ?, ?, ?, 1, 1, 0, ?, ?)
                """,
                (
                    "Modelo migrado",
                    assinatura,
                    "Mapeamento anterior",
                    colunas,
                    mapeamento,
                    criado or agora,
                    atualizado or agora
                )
            )

    @staticmethod
    def suggested_name(filename: str | None) -> str:
        stem = os.path.splitext(os.path.basename(filename or ""))[0]
        text = re.sub(r"[_-]+", " ", stem).strip()
        return text.title() if text else "Novo modelo de importação"

    @staticmethod
    def _row_to_dict(row):
        if not row:
            return None
        return {
            "id": row[0],
            "nome": row[1],
            "assinatura": row[2],
            "arquivo_referencia": row[3],
            "origem": row[4],
            "colunas": json.loads(row[5]),
            "mapeamento": json.loads(row[6]),
            "confirmado": bool(row[7]),
            "ativo": bool(row[8]),
            "utilizacoes": row[9],
            "criado_em": row[10],
            "atualizado_em": row[11],
            "ultimo_uso_em": row[12],
        }

    def match(self, colunas, *, count_usage: bool = True) -> dict | None:
        if count_usage:
            self.ensure_schema()
        else:
            conn = sqlite3.connect(self.database_path)
            try:
                exists = conn.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = 'perfis_importacao'
                    """
                ).fetchone()
            finally:
                conn.close()
            if not exists:
                return None
        assinatura = assinatura_colunas(colunas)
        agora = datetime.now().isoformat(timespec="seconds")
        conn = sqlite3.connect(self.database_path)
        try:
            row = conn.execute(
                """
                SELECT id, nome, assinatura, arquivo_referencia, origem,
                       colunas_json, mapeamento_json, confirmado, ativo,
                       utilizacoes, criado_em, atualizado_em, ultimo_uso_em
                FROM perfis_importacao
                WHERE assinatura = ? AND ativo = 1
                """,
                (assinatura,)
            ).fetchone()
            profile = self._row_to_dict(row)
            if not profile:
                return None
            names = {str(column).strip() for column in colunas}
            if any(
                column not in names
                for column in profile["mapeamento"].values()
            ):
                return None
            if count_usage:
                conn.execute(
                    """
                    UPDATE perfis_importacao
                    SET utilizacoes = utilizacoes + 1, ultimo_uso_em = ?
                    WHERE id = ?
                    """,
                    (agora, profile["id"])
                )
                conn.commit()
                profile["utilizacoes"] += 1
                profile["ultimo_uso_em"] = agora
            return profile
        finally:
            conn.close()

    def get_by_signature(self, colunas) -> dict | None:
        self.ensure_schema()
        assinatura = assinatura_colunas(colunas)
        conn = sqlite3.connect(self.database_path)
        try:
            row = conn.execute(
                """
                SELECT id, nome, assinatura, arquivo_referencia, origem,
                       colunas_json, mapeamento_json, confirmado, ativo,
                       utilizacoes, criado_em, atualizado_em, ultimo_uso_em
                FROM perfis_importacao WHERE assinatura = ?
                """,
                (assinatura,)
            ).fetchone()
            return self._row_to_dict(row)
        finally:
            conn.close()

    def save(
        self,
        colunas,
        mapeamento: dict,
        *,
        nome: str | None = None,
        arquivo_referencia: str | None = None,
        origem: str | None = None,
        confirmado: bool = False
    ) -> dict:
        self.ensure_schema()
        assinatura = assinatura_colunas(colunas)
        agora = datetime.now().isoformat(timespec="seconds")
        nome = (nome or "").strip() or self.suggested_name(
            arquivo_referencia
        )
        conn = sqlite3.connect(self.database_path)
        try:
            conn.execute(
                """
                INSERT INTO perfis_importacao (
                    nome, assinatura, arquivo_referencia, origem,
                    colunas_json, mapeamento_json, confirmado, ativo,
                    utilizacoes, criado_em, atualizado_em
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 0, ?, ?)
                ON CONFLICT(assinatura) DO UPDATE SET
                    nome = CASE
                        WHEN excluded.confirmado = 1 THEN excluded.nome
                        ELSE perfis_importacao.nome
                    END,
                    arquivo_referencia = COALESCE(
                        excluded.arquivo_referencia,
                        perfis_importacao.arquivo_referencia
                    ),
                    origem = COALESCE(
                        excluded.origem,
                        perfis_importacao.origem
                    ),
                    colunas_json = excluded.colunas_json,
                    mapeamento_json = excluded.mapeamento_json,
                    confirmado = MAX(
                        perfis_importacao.confirmado,
                        excluded.confirmado
                    ),
                    ativo = 1,
                    atualizado_em = excluded.atualizado_em
                """,
                (
                    nome,
                    assinatura,
                    arquivo_referencia,
                    origem,
                    json.dumps(
                        [str(column).strip() for column in colunas],
                        ensure_ascii=False
                    ),
                    json.dumps(mapeamento, ensure_ascii=False),
                    int(confirmado),
                    agora,
                    agora
                )
            )
            conn.commit()
        finally:
            conn.close()
        return self.get_by_signature(colunas)

    def list(self, *, active_only=True) -> list[dict]:
        self.ensure_schema()
        conn = sqlite3.connect(self.database_path)
        try:
            query = """
                SELECT id, nome, assinatura, arquivo_referencia, origem,
                       colunas_json, mapeamento_json, confirmado, ativo,
                       utilizacoes, criado_em, atualizado_em, ultimo_uso_em
                FROM perfis_importacao
            """
            if active_only:
                query += " WHERE ativo = 1"
            query += " ORDER BY nome COLLATE NOCASE"
            return [
                self._row_to_dict(row)
                for row in conn.execute(query).fetchall()
            ]
        finally:
            conn.close()

    def rename(self, profile_id: int, name: str) -> bool:
        name = str(name).strip()
        if not name:
            raise ValueError("O nome do perfil não pode ficar vazio.")
        self.ensure_schema()
        conn = sqlite3.connect(self.database_path)
        try:
            cursor = conn.execute(
                """
                UPDATE perfis_importacao
                SET nome = ?, confirmado = 1, atualizado_em = ?
                WHERE id = ?
                """,
                (
                    name,
                    datetime.now().isoformat(timespec="seconds"),
                    profile_id
                )
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def set_active(self, profile_id: int, active: bool) -> bool:
        self.ensure_schema()
        conn = sqlite3.connect(self.database_path)
        try:
            cursor = conn.execute(
                """
                UPDATE perfis_importacao
                SET ativo = ?, atualizado_em = ?
                WHERE id = ?
                """,
                (
                    int(active),
                    datetime.now().isoformat(timespec="seconds"),
                    profile_id
                )
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
