"""Modelo de usuário da autenticação."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from sqlite3 import Row


@dataclass(frozen=True, slots=True)
class User:
    id: int
    nome: str
    usuario: str
    email: str
    senha_hash: str
    perfil: str
    ativo: bool
    ultimo_login: datetime | None
    created_at: datetime

    @classmethod
    def from_row(cls, row: Row) -> "User":
        return cls(
            id=row["id"],
            nome=row["nome"],
            usuario=row["usuario"],
            email=row["email"],
            senha_hash=row["senha_hash"],
            perfil=row["perfil"],
            ativo=bool(row["ativo"]),
            ultimo_login=(
                datetime.fromisoformat(row["ultimo_login"])
                if row["ultimo_login"] else None
            ),
            created_at=datetime.fromisoformat(row["created_at"])
        )

    @property
    def iniciais(self) -> str:
        partes = [parte for parte in self.nome.split() if parte]
        return "".join(parte[0] for parte in partes[:2]).upper() or "US"
