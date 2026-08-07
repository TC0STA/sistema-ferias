"""Rotas e barreira central de autenticação."""

from __future__ import annotations

from urllib.parse import urlsplit

from flask import (
    Blueprint, flash, g, redirect, render_template, request, url_for
)

import backend
from decorators import login_required
from services.auth_service import (
    authenticate,
    current_user,
    end_user_session,
    get_csrf_token,
    load_current_user,
    start_user_session,
    validate_csrf_token,
)


bp = Blueprint("auth", __name__)

ALL_PROFILES = frozenset({"admin", "rh", "gestor", "consulta"})
ADMIN_RH = frozenset({"admin", "rh"})
ADMIN_GESTOR = frozenset({"admin", "gestor"})

MENU_ACCESS = {
    "dashboard": ALL_PROFILES,
    "importacao": ADMIN_RH,
    "calendario": frozenset({"admin", "rh", "gestor"}),
    "colaboradores": ADMIN_RH,
    "historico": ADMIN_RH,
    "relatorios": frozenset({"admin", "rh", "gestor"}),
    "auditoria": frozenset({"admin"}),
    "configuracoes": frozenset({"admin"}),
    "pesquisa": ADMIN_RH,
}


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
        ("/alertas", ADMIN_RH),
        ("/operacoes", ADMIN_RH),
        ("/detalhe", ADMIN_RH),
        ("/calendario", MENU_ACCESS["calendario"]),
        ("/colaboradores", MENU_ACCESS["colaboradores"]),
        ("/historico", MENU_ACCESS["historico"]),
        ("/relatorios", MENU_ACCESS["relatorios"]),
        ("/auditoria", MENU_ACCESS["auditoria"]),
        ("/configuracoes", MENU_ACCESS["configuracoes"]),
        ("/backup", MENU_ACCESS["configuracoes"]),
        ("/sobre", MENU_ACCESS["configuracoes"]),
        ("/manutencao", MENU_ACCESS["configuracoes"]),
        ("/pesquisa", MENU_ACCESS["pesquisa"]),
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
    if request.endpoint in {"auth.login", "static"}:
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
        return bool(user and user.perfil in MENU_ACCESS.get(area, frozenset()))

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
