"""Fluxo de solicitações de desligamento de colaboradores."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

import backend
from decorators import admin_required, login_required, permission_required
from services.auth_service import current_user, get_user_service, validate_csrf_token
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


def _form_values() -> dict:
    user_id_value = request.form.get("user_id", "").strip()
    user_id = None
    selected_user = None
    if user_id_value:
        try:
            user_id = int(user_id_value)
        except ValueError as error:
            raise ValueError("Selecione um usuário válido.") from error
        selected_user = get_user_service().get_by_id(user_id)
        if selected_user is None:
            raise ValueError("O usuário selecionado não existe.")
        if not selected_user.ativo:
            raise ValueError("O usuário selecionado já está inativo.")

    nome = selected_user.nome if selected_user else request.form.get("nome", "").strip()
    username = (
        selected_user.usuario
        if selected_user else request.form.get("usuario", "").strip()
    )
    email = selected_user.email if selected_user else request.form.get("email", "").strip()
    profile = selected_user.perfil if selected_user else request.form.get("perfil", "").strip()
    if not nome or not username:
        raise ValueError("Nome e usuário são obrigatórios.")
    if not is_valid_email(email):
        raise ValueError("Informe um e-mail válido.")
    try:
        termination_date = date.fromisoformat(
            request.form.get("data_desligamento", "")
        )
    except ValueError as error:
        raise ValueError("Informe uma data de desligamento válida.") from error
    return {
        "user_id": user_id,
        "nome": nome,
        "usuario": username,
        "email": email,
        "perfil": profile,
        "filial": request.form.get("filial", "").strip(),
        "departamento": request.form.get("departamento", "").strip(),
        "data_desligamento": termination_date,
        "observacao": request.form.get("observacao", "").strip(),
    }


def _audit(action: str, record, extra: str = "") -> None:
    detail = (
        f"Desligamento #{record.id}; usuário afetado: "
        f"{record.nome} ({record.usuario}); status: {record.status}"
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
    requester_id = None if actor.perfil == "admin" else actor.id
    status = request.args.get("status", "").strip()
    if status and status not in TERMINATION_STATUSES:
        status = ""
    service = get_termination_service()
    records = service.list_all(
        solicitado_por_id=requester_id,
        search=request.args.get("q", ""),
        status=status,
        filial=request.args.get("filial", ""),
    )
    return render_template(
        "desligamentos.html",
        desligamentos=records,
        resumo=service.summary(solicitado_por_id=requester_id),
        filiais=service.branches(solicitado_por_id=requester_id),
        usuarios=[user for user in get_user_service().list_all() if user.ativo],
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
            **_form_values(),
            solicitado_por_id=actor.id,
            solicitado_por=actor.nome,
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
    users = get_user_service()
    try:
        _require_csrf()
        record = service.get_by_id(request_id)
        if record is None:
            raise ValueError("Solicitação de desligamento não encontrada.")
        if record.status != "Pendente":
            raise ValueError("A solicitação já foi processada.")
        if record.user_id is None:
            raise ValueError(
                "Associe a solicitação a um usuário antes de confirmar."
            )
        target = users.get_by_id(record.user_id)
        if target is None:
            raise ValueError("O usuário associado não existe mais.")
        if target.id == current_user().id:
            raise ValueError("Você não pode desativar a própria conta.")
        if not target.ativo:
            raise ValueError("Este usuário já está inativo; nenhuma ação foi repetida.")
        users.set_active(target.id, False)
        try:
            record = service.mark_deactivated(request_id, current_user().nome)
        except Exception:
            users.set_active(target.id, True)
            raise
    except ValueError as error:
        flash(str(error), "error")
        return _redirect()
    _audit(
        "Confirmou desativação por desligamento",
        record,
        f"Administrador responsável: {current_user().nome}",
    )
    flash(
        f"Usuário {record.usuario} desativado no Fokus Férias.", "success"
    )
    return _redirect()
