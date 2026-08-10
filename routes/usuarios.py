"""Administração dos usuários que acessam o Fokus Férias."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

import backend
from decorators import admin_required, login_required
from services.auth_service import (
    current_user,
    get_user_service,
    validate_csrf_token,
)
from services.user_service import VALID_PROFILES, is_valid_email


bp = Blueprint("usuarios", __name__)
PROFILE_LABELS = {
    "admin": "Administrador",
    "rh": "RH / DP",
    "gestor": "Gestor",
    "consulta": "Consulta",
}


def _csrf_is_valid() -> bool:
    return validate_csrf_token(request.form.get("csrf_token", ""))


def _redirect():
    return redirect(url_for("usuarios.listar"))


def _status_from_form() -> bool:
    status = request.form.get("ativo", "")
    if status not in {"0", "1"}:
        raise ValueError("Selecione um status válido.")
    return status == "1"


def _audit(action: str, affected_user, extra: str = "") -> None:
    detail = f"Usuário afetado: {affected_user.nome} ({affected_user.usuario})"
    if extra:
        detail += f"; {extra}"
    backend.registrar_auditoria(
        action,
        detail,
        usuario=current_user().nome,
    )


@bp.route("/usuarios")
@login_required
@admin_required
def listar():
    agora = datetime.now()
    return render_template(
        "usuarios.html",
        usuarios=get_user_service().list_all(),
        profile_labels=PROFILE_LABELS,
        data_hoje=agora.strftime("%d/%m/%Y"),
    )


@bp.route("/usuarios/criar", methods=["POST"])
@login_required
@admin_required
def criar():
    if not _csrf_is_valid():
        flash("A sessão do formulário expirou. Tente novamente.", "error")
        return _redirect()

    service = get_user_service()
    nome = request.form.get("nome", "").strip()
    username = request.form.get("usuario", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("senha", "")
    confirmation = request.form.get("confirmar_senha", "")
    profile = request.form.get("perfil", "").strip()
    try:
        active = _status_from_form()
        if not nome:
            raise ValueError("O nome é obrigatório.")
        if not username:
            raise ValueError("O usuário é obrigatório.")
        if not is_valid_email(email):
            raise ValueError("Informe um e-mail válido.")
        if len(password) < 8:
            raise ValueError("A senha deve ter no mínimo 8 caracteres.")
        if password != confirmation:
            raise ValueError("A confirmação da senha não confere.")
        if profile not in VALID_PROFILES:
            raise ValueError("Selecione um perfil válido.")
        if service.get_by_username(username):
            raise ValueError("Este usuário já está cadastrado.")
        if service.get_by_email(email):
            raise ValueError("Este e-mail já está cadastrado.")
        user = service.create(
            nome=nome,
            usuario=username,
            email=email,
            senha=password,
            perfil=profile,
            ativo=active,
        )
    except ValueError as error:
        flash(str(error), "error")
        return _redirect()

    _audit(
        "Criação de usuário",
        user,
        f"Perfil: {PROFILE_LABELS[user.perfil]}; Status: {'Ativo' if user.ativo else 'Inativo'}",
    )
    flash(f"Usuário {user.usuario} criado com sucesso.", "success")
    return _redirect()


@bp.route("/usuarios/<int:user_id>/editar", methods=["POST"])
@login_required
@admin_required
def editar(user_id: int):
    if not _csrf_is_valid():
        flash("A sessão do formulário expirou. Tente novamente.", "error")
        return _redirect()

    service = get_user_service()
    original = service.get_by_id(user_id)
    if original is None:
        flash("Usuário não encontrado.", "error")
        return _redirect()

    nome = request.form.get("nome", "").strip()
    email = request.form.get("email", "").strip()
    profile = request.form.get("perfil", "").strip()
    try:
        active = _status_from_form()
        if user_id == current_user().id and not active:
            raise ValueError("Você não pode desativar a própria conta.")
        updated = service.update(
            user_id,
            nome=nome,
            email=email,
            perfil=profile,
            ativo=active,
        )
    except ValueError as error:
        flash(str(error), "error")
        return _redirect()

    _audit("Edição de usuário", updated)
    if original.perfil != updated.perfil:
        _audit(
            "Alteração de perfil",
            updated,
            f"De {PROFILE_LABELS[original.perfil]} para {PROFILE_LABELS[updated.perfil]}",
        )
    if original.ativo != updated.ativo:
        action = "Ativação de usuário" if updated.ativo else "Desativação de usuário"
        _audit(action, updated)
    flash(f"Usuário {updated.usuario} atualizado com sucesso.", "success")
    return _redirect()


@bp.route("/usuarios/<int:user_id>/status", methods=["POST"])
@login_required
@admin_required
def alterar_status(user_id: int):
    if not _csrf_is_valid():
        flash("A sessão do formulário expirou. Tente novamente.", "error")
        return _redirect()

    service = get_user_service()
    target = service.get_by_id(user_id)
    if target is None:
        flash("Usuário não encontrado.", "error")
        return _redirect()
    try:
        active = _status_from_form()
        if user_id == current_user().id and not active:
            raise ValueError("Você não pode desativar a própria conta.")
        updated = service.set_active(user_id, active)
    except ValueError as error:
        flash(str(error), "error")
        return _redirect()

    action = "Ativação de usuário" if updated.ativo else "Desativação de usuário"
    _audit(action, updated)
    flash(
        f"Usuário {updated.usuario} {'ativado' if updated.ativo else 'desativado'} com sucesso.",
        "success",
    )
    return _redirect()


@bp.route("/usuarios/<int:user_id>/redefinir-senha", methods=["POST"])
@login_required
@admin_required
def redefinir_senha(user_id: int):
    if not _csrf_is_valid():
        flash("A sessão do formulário expirou. Tente novamente.", "error")
        return _redirect()

    password = request.form.get("senha", "")
    confirmation = request.form.get("confirmar_senha", "")
    try:
        if len(password) < 8:
            raise ValueError("A senha deve ter no mínimo 8 caracteres.")
        if password != confirmation:
            raise ValueError("A confirmação da senha não confere.")
        updated = get_user_service().reset_password(user_id, password)
    except ValueError as error:
        flash(str(error), "error")
        return _redirect()

    _audit("Redefinição de senha", updated)
    flash(f"Senha de {updated.usuario} redefinida com sucesso.", "success")
    return _redirect()
