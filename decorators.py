"""Decorators reutilizáveis de autenticação e autorização."""

from __future__ import annotations

from functools import wraps

from flask import jsonify, redirect, render_template, request, url_for

from services.auth_service import current_user


def _is_api_request() -> bool:
    return request.path.startswith("/api/") or request.is_json


def _unauthenticated_response():
    if _is_api_request():
        return jsonify({
            "ok": False,
            "erro": "Autenticação necessária."
        }), 401
    return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))


def _forbidden_response():
    if _is_api_request():
        return jsonify({
            "ok": False,
            "erro": "Seu perfil não possui acesso a este recurso."
        }), 403
    return render_template("403.html", current_user=current_user()), 403


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return _unauthenticated_response()
        return view(*args, **kwargs)
    return wrapped


def roles_required(*profiles):
    allowed = frozenset(profiles)

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return _unauthenticated_response()
            if user.perfil not in allowed:
                return _forbidden_response()
            return view(*args, **kwargs)
        return wrapped
    return decorator


def admin_required(view):
    return roles_required("admin")(view)


def rh_required(view):
    return roles_required("admin", "rh")(view)


__all__ = [
    "login_required", "admin_required", "rh_required", "roles_required"
]
