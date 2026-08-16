"""Rotas e barreira central de autenticação."""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)

import backend
from decorators import login_required
from permissions import (
    ADMIN_GESTOR,
    ADMIN_RH,
    ALL_PROFILES,
    PERMISSION_PROFILES,
    has_permission,
)
from services.auth_service import (
    authenticate,
    current_user,
    end_user_session,
    get_csrf_token,
    get_user_service,
    load_current_user,
    start_user_session,
    validate_csrf_token,
)


bp = Blueprint("auth", __name__)

MENU_ACCESS = PERMISSION_PROFILES


def _requested_profiles(path: str) -> frozenset[str]:
    if path == "/":
        return ALL_PROFILES
    rules = (
        ("/api/importacao", ADMIN_RH),
        ("/upload", ADMIN_RH),
        ("/importar", ADMIN_RH),
        ("/dashboard/executivo", ADMIN_GESTOR),
        ("/dashboard/rh", ADMIN_RH),
        ("/dashboard/ti", frozenset({"admin"})),
        ("/dashboard", ALL_PROFILES),
        ("/alertas", ALL_PROFILES),
        ("/operacoes", ALL_PROFILES),
        ("/detalhe", ALL_PROFILES),
        ("/calendario", MENU_ACCESS["calendario"]),
        ("/colaboradores", MENU_ACCESS["colaboradores"]),
        ("/historico", MENU_ACCESS["historico"]),
        ("/relatorios", MENU_ACCESS["relatorios"]),
        ("/auditoria", MENU_ACCESS["auditoria"]),
        ("/usuarios", MENU_ACCESS["usuarios"]),
        ("/configuracoes", MENU_ACCESS["configuracoes"]),
        ("/backup", MENU_ACCESS["configuracoes"]),
        ("/sobre", MENU_ACCESS["configuracoes"]),
        ("/manutencao", MENU_ACCESS["configuracoes"]),
        ("/pesquisa", MENU_ACCESS["pesquisa"]),
        ("/minha-conta", ALL_PROFILES),
        ("/api/versao-dados", ALL_PROFILES),
        ("/imagens", ALL_PROFILES),
        ("/uploads", ALL_PROFILES),
    )
    for prefix, profiles in rules:
        if path == prefix or path.startswith(prefix + "/"):
            return profiles
    return frozenset({"admin"})


def _safe_next_url(value: str | None) -> str:
    if not value:
        return url_for("dashboard.dashboard")
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc or not value.startswith("/"):
        return url_for("dashboard.dashboard")
    return value


@bp.before_app_request
def enforce_access_control():
    user = load_current_user()
    if request.endpoint in {"auth.login", "auth.logout", "static"}:
        return None
    if request.path.startswith("/static/"):
        return None
    if user is None:
        if request.path.startswith("/api/") or request.is_json:
            return {"ok": False, "erro": "Autenticação necessária."}, 401
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))

    allowed = _requested_profiles(request.path)
    if user.perfil not in allowed:
        if request.path.startswith("/api/") or request.is_json:
            return {
                "ok": False,
                "erro": "Seu perfil não possui acesso a este recurso."
            }, 403
        return render_template("403.html"), 403
    return None


@bp.app_context_processor
def auth_template_context():
    user = getattr(g, "current_user", None)

    def can_access(area: str) -> bool:
        return bool(user and has_permission(user.perfil, area))

    return {
        "current_user": user,
        "can_access": can_access,
        "csrf_token": get_csrf_token
    }


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user() is not None:
        return redirect(_safe_next_url(request.args.get("next")))

    erro = None
    username = ""
    next_url = _safe_next_url(request.args.get("next"))
    if request.method == "POST":
        username = request.form.get("usuario", "").strip()
        password = request.form.get("senha", "")
        next_url = _safe_next_url(request.form.get("next"))

        if not validate_csrf_token(request.form.get("csrf_token", "")):
            erro = "A sessão do formulário expirou. Tente novamente."
        else:
            user = authenticate(username, password)
            if user is None:
                erro = "Usuário ou senha inválidos."
                backend.registrar_auditoria(
                    "Falha de login",
                    f"Usuário informado: {username or 'não informado'}",
                    usuario=username or "Anônimo",
                    resultado="Falha"
                )
            else:
                start_user_session(user)
                backend.registrar_auditoria(
                    "Login realizado",
                    f"Perfil: {user.perfil}",
                    usuario=user.nome
                )
                return redirect(next_url)

    return render_template(
        "login.html",
        erro=erro,
        usuario=username,
        next_url=next_url
    )


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    user = current_user()
    if not validate_csrf_token(request.form.get("csrf_token", "")):
        flash("Não foi possível encerrar a sessão. Tente novamente.", "error")
        return redirect(url_for("dashboard.dashboard"))
    backend.registrar_auditoria(
        "Logout realizado",
        f"Perfil: {user.perfil}",
        usuario=user.nome
    )
    end_user_session()
    return redirect(url_for("auth.login"))


@bp.route("/minha-conta", methods=["GET", "POST"])
@login_required
def minha_conta():
    user = current_user()
    if request.method == "POST":
        current_password = request.form.get("senha_atual", "")
        new_password = request.form.get("nova_senha", "")
        confirmation = request.form.get("confirmar_nova_senha", "")

        if not validate_csrf_token(request.form.get("csrf_token", "")):
            flash("A sessão do formulário expirou. Tente novamente.", "error")
        elif not current_password:
            flash("Informe a senha atual.", "error")
        elif len(new_password) < 8:
            flash("A nova senha deve ter no mínimo 8 caracteres.", "error")
        elif new_password != confirmation:
            flash("A confirmação da nova senha não confere.", "error")
        elif not get_user_service().change_password(
            user.id, current_password, new_password
        ):
            flash("A senha atual está incorreta.", "error")
        else:
            backend.registrar_auditoria(
                "Senha alterada",
                "Senha da própria conta atualizada com sucesso.",
                usuario=user.nome
            )
            flash("Senha alterada com sucesso.", "success")

        return redirect(url_for("auth.minha_conta") + "#alterar-senha")

    return render_template("minha_conta.html")
