"""Modelo de solicitação de desligamento."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class TerminationRequest:
    id: int
    user_id: int | None
    nome: str
    usuario: str
    email: str
    perfil: str
    filial: str
    departamento: str
    data_desligamento: date
    observacao: str
    status: str
    solicitado_por_id: int
    solicitado_por: str
    solicitado_em: datetime
    desativado_por: str | None
    desativado_em: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "TerminationRequest":
        def parse_date(value: Any) -> date:
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            return date.fromisoformat(str(value))

        def parse_datetime(value: Any) -> datetime | None:
            if value is None or isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value))

        solicitado_em = parse_datetime(row["solicitado_em"])
        created_at = parse_datetime(row["created_at"])
        updated_at = parse_datetime(row["updated_at"])
        if solicitado_em is None or created_at is None or updated_at is None:
            raise ValueError("A solicitação possui datas obrigatórias inválidas.")
        return cls(
            id=int(row["id"]),
            user_id=int(row["user_id"]) if row["user_id"] is not None else None,
            nome=str(row["nome"]),
            usuario=str(row["usuario"]),
            email=str(row["email"]),
            perfil=str(row["perfil"] or ""),
            filial=str(row["filial"] or ""),
            departamento=str(row["departamento"] or ""),
            data_desligamento=parse_date(row["data_desligamento"]),
            observacao=str(row["observacao"] or ""),
            status=str(row["status"]),
            solicitado_por_id=int(row["solicitado_por_id"]),
            solicitado_por=str(row["solicitado_por"]),
            solicitado_em=solicitado_em,
            desativado_por=(
                str(row["desativado_por"])
                if row["desativado_por"] is not None else None
            ),
            desativado_em=parse_datetime(row["desativado_em"]),
            created_at=created_at,
            updated_at=updated_at,
        )

