"""Matriz central de permissões dos perfis do Fokus Férias."""

from __future__ import annotations


ALL_PROFILES = frozenset({"admin", "rh", "gestor", "consulta"})
ADMIN_ONLY = frozenset({"admin"})
ADMIN_RH = frozenset({"admin", "rh"})
ADMIN_GESTOR = frozenset({"admin", "gestor"})

PERMISSION_PROFILES = {
    "dashboard": ALL_PROFILES,
    "importacao": ADMIN_RH,
    "calendario": ALL_PROFILES,
    "colaboradores": ALL_PROFILES,
    "editar_colaboradores": ADMIN_RH,
    "historico": ADMIN_RH,
    "relatorios": ALL_PROFILES,
    "auditoria": ADMIN_ONLY,
    "usuarios": ADMIN_ONLY,
    "configuracoes": ADMIN_ONLY,
    "pesquisa": ALL_PROFILES,
}


def has_permission(profile: str, permission: str) -> bool:
    return profile in PERMISSION_PROFILES.get(permission, frozenset())
