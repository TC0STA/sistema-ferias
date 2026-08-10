"""Registro central dos Blueprints da aplicação."""

from flask import url_for

from routes.auth import bp as auth_bp
from routes.configuracoes import bp as configuracoes_bp
from routes.dashboard import bp as dashboard_bp
from routes.historico import bp as historico_bp
from routes.importacao import bp as importacao_bp
from routes.pesquisa import bp as pesquisa_bp
from routes.relatorios import bp as relatorios_bp
from routes.usuarios import bp as usuarios_bp
from services.auth_service import configure_auth


BLUEPRINTS = (
    auth_bp,
    dashboard_bp,
    importacao_bp,
    historico_bp,
    relatorios_bp,
    configuracoes_bp,
    pesquisa_bp,
    usuarios_bp,
)


def register_blueprints(app):
    """Registra módulos e mantém compatibilidade com endpoints sem prefixo."""
    configure_auth(app)
    legacy_endpoints = {}
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)

    for rule in app.url_map.iter_rules():
        if "." in rule.endpoint:
            legacy_endpoints.setdefault(
                rule.endpoint.rsplit(".", 1)[-1], rule.endpoint
            )

    def build_legacy_url(_error, endpoint, values):
        qualified = legacy_endpoints.get(endpoint)
        if qualified is None:
            return None
        return url_for(qualified, **values)

    app.url_build_error_handlers.append(build_legacy_url)
