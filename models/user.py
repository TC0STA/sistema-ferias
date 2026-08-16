"""Modelo de usuário da autenticação."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


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
    def from_row(cls, row: Mapping[str, Any]) -> "User":
        def parse_datetime(value: Any) -> datetime | None:
            if value is None or isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value))

        created_at = parse_datetime(row["created_at"])
        if created_at is None:
            raise ValueError("O usuário não possui data de criação válida.")

        return cls(
            id=int(row["id"]),
            nome=str(row["nome"]),
            usuario=str(row["usuario"]),
            email=str(row["email"]),
            senha_hash=str(row["senha_hash"]),
            perfil=str(row["perfil"]),
            ativo=bool(row["ativo"]),
            ultimo_login=parse_datetime(row["ultimo_login"]),
            created_at=created_at,
        )

    @property
    def iniciais(self) -> str:
        partes = [parte for parte in self.nome.split() if parte]
        return "".join(parte[0] for parte in partes[:2]).upper() or "US"
