"""Modelo de solicitação de desligamento."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class TerminationRequest:
    id: int
    nome: str
    usuario_ad: str
    email: str
    perfil: str
    filial: str
    departamento: str
    data_desligamento: date
    observacao: str
    status: str
    informado_por: str
    data_solicitacao: datetime
    confirmado_por: str | None
    data_confirmacao: datetime | None
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

        data_solicitacao = parse_datetime(row["data_solicitacao"])
        created_at = parse_datetime(row["created_at"])
        updated_at = parse_datetime(row["updated_at"])
        if data_solicitacao is None or created_at is None or updated_at is None:
            raise ValueError("A solicitação possui datas obrigatórias inválidas.")
        return cls(
            id=int(row["id"]),
            nome=str(row["nome"]),
            usuario_ad=str(row["usuario_ad"]),
            email=str(row["email"]),
            perfil=str(row["perfil"] or ""),
            filial=str(row["filial"] or ""),
            departamento=str(row["departamento"] or ""),
            data_desligamento=parse_date(row["data_desligamento"]),
            observacao=str(row["observacao"] or ""),
            status=str(row["status"]),
            informado_por=str(row["informado_por"]),
            data_solicitacao=data_solicitacao,
            confirmado_por=(
                str(row["confirmado_por"])
                if row["confirmado_por"] is not None else None
            ),
            data_confirmacao=parse_datetime(row["data_confirmacao"]),
            created_at=created_at,
            updated_at=updated_at,
        )

