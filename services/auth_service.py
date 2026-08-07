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
USER_DATABASE_PATH = BASE_DIR / "database" / "usuarios.db"
SESSION_SECRET_PATH = BASE_DIR / "database" / ".session_secret"


def get_user_service() -> UserService:
    registered = current_app.extensions.get("fokus_user_service")
    if registered is not None:
        return registered
    path = current_app.config.get("USER_DATABASE_PATH", USER_DATABASE_PATH)
    return UserService(path)


def _load_or_create_session_secret() -> str:
    configured = os.environ.get("FOKUS_SECRET_KEY", "").strip()
    if configured:
        return configured
    SESSION_SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SESSION_SECRET_PATH.exists():
        return SESSION_SECRET_PATH.read_text(encoding="utf-8").strip()
    secret = secrets.token_urlsafe(48)
    SESSION_SECRET_PATH.write_text(secret, encoding="utf-8")
    return secret


def configure_auth(app) -> None:
    app.config.setdefault("USER_DATABASE_PATH", str(USER_DATABASE_PATH))
    app.config.update(
        SECRET_KEY=app.config.get("SECRET_KEY") or _load_or_create_session_secret(),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax"
    )
    service = UserService(app.config["USER_DATABASE_PATH"])
    service.ensure_schema()
    app.extensions["fokus_user_service"] = service
    if service.ensure_default_admin():
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
