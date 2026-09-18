"""Escopo central de acesso às importações de férias."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from flask import current_app

from models.user import User
from services.auth_service import current_user
from services.import_log import ImportLogger


@dataclass(frozen=True, slots=True)
class ImportAccessScope:
    """Predicado de acesso derivado exclusivamente do usuário autenticado."""

    usuario_id: int | None
    administrador: bool
    autenticado: bool

    @property
    def condicao_sql(self) -> str:
        if not self.autenticado:
            return "1 = 0"
        if self.administrador:
            return "1 = 1"
        return "usuario_id = ?"

    @property
    def parametros_sql(self) -> tuple[int, ...]:
        if not self.autenticado or self.administrador:
            return ()
        return (self.usuario_id,)


def obter_usuario_atual() -> User | None:
    """Retorna somente um usuário autenticado e ainda ativo."""
    user = current_user()
    if user is None or not user.ativo:
        return None
    return user


def usuario_e_admin() -> bool:
    user = obter_usuario_atual()
    return bool(user and user.perfil == "admin")


def obter_escopo_importacoes() -> ImportAccessScope:
    user = obter_usuario_atual()
    if user is None:
        return ImportAccessScope(
            usuario_id=None,
            administrador=False,
            autenticado=False
        )
    return ImportAccessScope(
        usuario_id=user.id,
        administrador=usuario_e_admin(),
        autenticado=True
    )


def _database_path() -> str:
    database_path = current_app.config.get("DATABASE_PATH")
    if not database_path:
        raise RuntimeError("O banco de dados de férias não foi configurado.")
    return str(database_path)


def listar_importacoes_permitidas() -> list[dict]:
    """Lista importações pertencentes ao escopo autenticado atual."""
    scope = obter_escopo_importacoes()
    if not scope.autenticado:
        return []

    database_path = _database_path()
    ImportLogger(database_path).ensure_schema()
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            f"SELECT * FROM importacoes WHERE {scope.condicao_sql} "
            "ORDER BY versao",
            scope.parametros_sql
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def usuario_pode_acessar_importacao(importacao_id: int) -> bool:
    """Verifica um recurso pelo ID sem aceitar proprietário do cliente."""
    scope = obter_escopo_importacoes()
    if not scope.autenticado:
        return False
    try:
        importacao_id = int(importacao_id)
    except (TypeError, ValueError):
        return False
    if importacao_id <= 0:
        return False

    database_path = _database_path()
    ImportLogger(database_path).ensure_schema()
    conn = sqlite3.connect(database_path)
    try:
        row = conn.execute(
            f"SELECT 1 FROM importacoes WHERE id = ? "
            f"AND {scope.condicao_sql}",
            (importacao_id, *scope.parametros_sql)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


__all__ = [
    "ImportAccessScope",
    "listar_importacoes_permitidas",
    "obter_escopo_importacoes",
    "obter_usuario_atual",
    "usuario_e_admin",
    "usuario_pode_acessar_importacao",
]
