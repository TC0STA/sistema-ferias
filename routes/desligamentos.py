"""Fluxo de solicitações de desligamento de colaboradores."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

import backend
from decorators import admin_required, login_required, permission_required
from services.auth_service import current_user, validate_csrf_token
from services.termination_service import (
    TERMINATION_STATUSES,
    get_termination_service,
)
from services.user_service import is_valid_email


bp = Blueprint("desligamentos", __name__)


def _redirect():
    return redirect(url_for("desligamentos.listar"))


def _require_csrf() -> None:
    if not validate_csrf_token(request.form.get("csrf_token", "")):
        raise ValueError("A sessão do formulário expirou. Tente novamente.")


def _form_values(*, include_identity: bool = True) -> dict:
    nome = request.form.get("nome", "").strip()
    username = request.form.get("usuario_ad", "").strip() if include_identity else ""
    email = request.form.get("email", "").strip() if include_identity else ""
    profile = request.form.get("perfil", "").strip()
    if not nome:
        raise ValueError("Nome do colaborador é obrigatório.")
    if include_identity and not username:
        raise ValueError("Usuário AD é obrigatório.")
    if include_identity and not is_valid_email(email):
        raise ValueError("Informe um e-mail válido.")
    try:
        termination_date = date.fromisoformat(
            request.form.get("data_desligamento", "")
        )
    except ValueError as error:
        raise ValueError("Informe uma data de desligamento válida.") from error
    return {
        "nome": nome,
        "usuario_ad": username,
        "email": email,
        "perfil": profile,
        "filial": request.form.get("filial", "").strip() if include_identity else "",
        "departamento": request.form.get("departamento", "").strip(),
        "data_desligamento": termination_date,
        "observacao": request.form.get("observacao", "").strip(),
    }


def _audit(action: str, record, extra: str = "") -> None:
    detail = (
        f"Desligamento #{record.id}; usuário afetado: "
        f"{record.nome} ({record.usuario_ad}); status: {record.status}"
    )
    if extra:
        detail += f"; {extra}"
    backend.registrar_auditoria(
        action, detail, usuario=current_user().nome
    )


@bp.route("/desligamentos")
@login_required
@permission_required("desligamentos")
def listar():
    actor = current_user()
    status = request.args.get("status", "").strip()
    if status and status not in TERMINATION_STATUSES:
        status = ""
    service = get_termination_service()
    records = service.list_all(
        search=request.args.get("q", ""),
        status=status,
        filial=request.args.get("filial", ""),
    )
    return render_template(
        "desligamentos.html",
        desligamentos=records,
        resumo=service.summary(),
        filiais=service.branches(),
        is_admin=actor.perfil == "admin",
        filtros={
            "q": request.args.get("q", ""),
            "status": status,
            "filial": request.args.get("filial", ""),
        },
    )


@bp.route("/desligamentos/criar", methods=["POST"])
@login_required
@permission_required("desligamentos")
def criar():
    try:
        _require_csrf()
        actor = current_user()
        record = get_termination_service().create(
            **_form_values(include_identity=False),
            informado_por=actor.nome,
        )
    except ValueError as error:
        flash(str(error), "error")
        return _redirect()
    _audit("Criou solicitação de desligamento", record)
    flash("Solicitação de desligamento criada com sucesso.", "success")
    return _redirect()


@bp.route("/desligamentos/<int:request_id>/editar", methods=["POST"])
@login_required
@admin_required
def editar(request_id: int):
    try:
        _require_csrf()
        record = get_termination_service().update_pending(
            request_id, **_form_values()
        )
    except ValueError as error:
        flash(str(error), "error")
        return _redirect()
    _audit("Editou solicitação de desligamento", record)
    flash("Solicitação atualizada com sucesso.", "success")
    return _redirect()


@bp.route("/desligamentos/<int:request_id>/cancelar", methods=["POST"])
@login_required
@admin_required
def cancelar(request_id: int):
    try:
        _require_csrf()
        record = get_termination_service().cancel(request_id)
    except ValueError as error:
        flash(str(error), "error")
        return _redirect()
    _audit("Cancelou solicitação de desligamento", record)
    flash("Solicitação cancelada e mantida no histórico.", "success")
    return _redirect()


@bp.route("/desligamentos/<int:request_id>/confirmar", methods=["POST"])
@login_required
@admin_required
def confirmar(request_id: int):
    service = get_termination_service()
    try:
        _require_csrf()
        record = service.get_by_id(request_id)
        if record is None:
            raise ValueError("Solicitação de desligamento não encontrada.")
        if record.status != "PENDENTE":
            raise ValueError("A solicitação já foi processada.")
        record = service.confirm(request_id, current_user().nome)
    except ValueError as error:
        flash(str(error), "error")
        return _redirect()
    _audit(
        "Confirmou desligamento",
        record,
        f"Administrador responsável: {current_user().nome}",
    )
    flash(f"Desligamento de {record.nome} confirmado com sucesso.", "success")
    return _redirect()
