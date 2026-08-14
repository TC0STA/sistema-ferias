"""Serviços de autenticação e sessão Flask."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from pathlib import Path

from flask import current_app, g, session
from werkzeug.security import check_password_hash

from models.user import User
from services.user_service import UserService


BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL_USER_DATABASE_PATH = BASE_DIR / "database" / "usuarios.db"
USER_DATABASE_PATH = LOCAL_USER_DATABASE_PATH
SESSION_SECRET_PATH = BASE_DIR / "database" / ".session_secret"
POSTGRES_SCHEMES = ("postgresql://", "postgres://")


def get_user_service() -> UserService:
    registered = current_app.extensions.get("fokus_user_service")
    if registered is None:
        raise RuntimeError("O serviço de usuários não foi inicializado.")
    return registered


def resolve_user_database(app) -> str | Path:
    """Seleciona PostgreSQL em produção e SQLite somente no ambiente local."""
    render = os.environ.get("RENDER", "").strip().lower() == "true"
    database_url = (
        app.config.get("DATABASE_URL")
        or os.environ.get("DATABASE_URL", "").strip()
    )
    if database_url:
        if not str(database_url).lower().startswith(POSTGRES_SCHEMES):
            raise RuntimeError("DATABASE_URL deve apontar para um banco PostgreSQL.")
        return str(database_url)

    if render:
        raise RuntimeError(
            "DATABASE_URL é obrigatória no Render e deve apontar para o "
            "PostgreSQL persistente."
        )

    explicit_path = app.config.get("USER_DATABASE_PATH")
    environment_path = os.environ.get("USER_DATABASE_PATH", "").strip()
    configured_path = explicit_path or environment_path

    if configured_path:
        path = Path(configured_path).expanduser()
        if not path.is_absolute():
            path = BASE_DIR / path
        return path

    return LOCAL_USER_DATABASE_PATH


def resolve_user_database_path(app) -> Path:
    """Compatibilidade: resolve somente a configuração SQLite local."""
    database = resolve_user_database(app)
    if isinstance(database, str) and database.lower().startswith(POSTGRES_SCHEMES):
        raise RuntimeError("A persistência configurada é PostgreSQL, não um arquivo.")
    return Path(database)


def _load_or_create_session_secret() -> str:
    configured = os.environ.get("FOKUS_SECRET_KEY", "").strip()
    if configured:
        return configured
    if os.environ.get("RENDER", "").strip().lower() == "true":
        raise RuntimeError(
            "FOKUS_SECRET_KEY é obrigatória no Render para manter sessões seguras."
        )
    SESSION_SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SESSION_SECRET_PATH.exists():
        return SESSION_SECRET_PATH.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(48)
    SESSION_SECRET_PATH.write_text(secret, encoding="utf-8")
    return secret


def configure_auth(app) -> None:
    user_database = resolve_user_database(app)
    if str(user_database).lower().startswith(POSTGRES_SCHEMES):
        app.config["DATABASE_URL"] = str(user_database)
    else:
        app.config["USER_DATABASE_PATH"] = str(user_database)
    app.config.update(
        SECRET_KEY=app.config.get("SECRET_KEY") or _load_or_create_session_secret(),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax"
    )
    service = UserService(user_database)
    default_admin_created = service.initialize()
    app.extensions["fokus_user_service"] = service
    if default_admin_created:
        print("[Fokus Férias] Usuário administrador criado: admin / admin123")


def authenticate(username: str, password: str) -> User | None:
    user = get_user_service().get_by_username(username)
    if not user or not user.ativo:
        return None
    if not check_password_hash(user.senha_hash, password):
        return None
    get_user_service().update_last_login(user.id)
    return get_user_service().get_by_id(user.id)


def start_user_session(user: User) -> None:
    session.clear()
    session.permanent = True
    session["user_id"] = user.id


def end_user_session() -> None:
    session.clear()


def load_current_user() -> User | None:
    user_id = session.get("user_id")
    user = get_user_service().get_by_id(user_id) if user_id else None
    if user and not user.ativo:
        session.clear()
        user = None
    g.current_user = user
    return user


def current_user() -> User | None:
    return getattr(g, "current_user", None)


def current_actor(default: str = "Sistema") -> str:
    user = current_user()
    return user.nome if user else default


def get_csrf_token() -> str:
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf_token(token: str) -> bool:
    expected = session.get("csrf_token", "")
    return bool(expected and token and secrets.compare_digest(expected, token))
