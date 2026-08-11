from __future__ import annotations

import sqlite3
from datetime import datetime


class ImportLogger:
    """Registra importações sem depender de Flask ou da interface."""

    def __init__(self, database_path: str):
        self.database_path = database_path

    def ensure_schema(self):
        conn = sqlite3.connect(self.database_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS importacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                versao INTEGER NOT NULL,
                arquivo TEXT NOT NULL,
                registros INTEGER NOT NULL,
                erros INTEGER NOT NULL DEFAULT 0,
                duracao_segundos REAL NOT NULL,
                usuario TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                novos INTEGER NOT NULL DEFAULT 0,
                removidos INTEGER NOT NULL DEFAULT 0,
                datas_alteradas INTEGER NOT NULL DEFAULT 0,
                sem_alteracoes INTEGER NOT NULL DEFAULT 0,
                hash_arquivo TEXT NOT NULL,
                arquivo_armazenado TEXT
            )
        """)
        colunas_importacoes = {
            item[1]
            for item in conn.execute("PRAGMA table_info(importacoes)").fetchall()
        }
        if "arquivo_armazenado" not in colunas_importacoes:
            conn.execute(
                "ALTER TABLE importacoes ADD COLUMN arquivo_armazenado TEXT"
            )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS importacao_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT NOT NULL,
                hora TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                usuario TEXT NOT NULL,
                arquivo TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                tempo_segundos REAL NOT NULL,
                erros INTEGER NOT NULL,
                versao INTEGER,
                ip TEXT NOT NULL,
                resultado TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def _inserir_log(
        self,
        conn,
        *,
        arquivo: str,
        quantidade: int,
        tempo_segundos: float,
        erros: int,
        usuario: str,
        ip: str,
        resultado: str,
        versao: int | None,
        agora: datetime
    ):
        conn.execute(
            """
            INSERT INTO importacao_logs (
                data, hora, criado_em, usuario, arquivo, quantidade,
                tempo_segundos, erros, versao, ip, resultado
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agora.strftime("%d/%m/%Y"),
                agora.strftime("%H:%M:%S"),
                agora.isoformat(timespec="seconds"),
                usuario,
                arquivo,
                quantidade,
                tempo_segundos,
                erros,
                versao,
                ip,
                resultado
            )
        )

    def record_failure(
        self,
        *,
        arquivo: str,
        quantidade: int,
        tempo_segundos: float,
        erros: int,
        usuario: str,
        ip: str,
        resultado: str = "Falha"
    ):
        self.ensure_schema()
        conn = sqlite3.connect(self.database_path)
        try:
            self._inserir_log(
                conn,
                arquivo=arquivo,
                quantidade=quantidade,
                tempo_segundos=tempo_segundos,
                erros=erros,
                usuario=usuario,
                ip=ip,
                resultado=resultado,
                versao=None,
                agora=datetime.now()
            )
            conn.commit()
        finally:
            conn.close()

    def record_success(
        self,
        *,
        arquivo: str,
        registros: int,
        erros: int,
        duracao_segundos: float,
        usuario: str,
        ip: str,
        comparacao: dict,
        hash_arquivo: str,
        arquivo_armazenado: str | None = None
    ) -> int:
        self.ensure_schema()
        conn = sqlite3.connect(self.database_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            agora = datetime.now()
            versao = conn.execute(
                "SELECT COALESCE(MAX(versao), 0) + 1 FROM importacoes"
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO importacoes (
                    versao, arquivo, registros, erros, duracao_segundos,
                    usuario, criado_em, novos, removidos, datas_alteradas,
                    sem_alteracoes, hash_arquivo, arquivo_armazenado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    versao,
                    arquivo,
                    registros,
                    erros,
                    duracao_segundos,
                    usuario,
                    agora.isoformat(timespec="seconds"),
                    comparacao.get("novos", 0),
                    comparacao.get("removidos", 0),
                    comparacao.get("alterados", 0),
                    comparacao.get("iguais", 0),
                    hash_arquivo,
                    arquivo_armazenado or arquivo
                )
            )
            self._inserir_log(
                conn,
                arquivo=arquivo,
                quantidade=registros,
                tempo_segundos=duracao_segundos,
                erros=erros,
                usuario=usuario,
                ip=ip,
                resultado="Sucesso",
                versao=versao,
                agora=agora
            )
            conn.commit()
            return versao
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
