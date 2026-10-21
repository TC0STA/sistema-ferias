"""Ponto de entrada da aplicação Fokus Férias."""

import os

from flask import Flask

import backend
from routes import register_blueprints
from services.monthly_theme import get_login_monthly_theme, get_monthly_theme


BASE_DIR = backend.BASE_DIR
UPLOAD_FOLDER = backend.UPLOAD_FOLDER
DATABASE_PATH = backend.DATABASE_PATH
VALIDACOES_DIR = backend.VALIDACOES_DIR
BACKUPS_DIR = backend.BACKUPS_DIR
CONFIGURACOES_PADRAO = backend.CONFIGURACOES_PADRAO


def create_app():
    app = Flask(__name__)
    app.config.from_mapping(
        BASE_DIR=BASE_DIR,
        UPLOAD_FOLDER=UPLOAD_FOLDER,
        DATABASE_PATH=DATABASE_PATH,
        VALIDACOES_DIR=VALIDACOES_DIR,
        BACKUPS_DIR=BACKUPS_DIR,
    )
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    register_blueprints(app)

    @app.context_processor
    def inject_monthly_theme():
        return {
            "monthly_theme": get_monthly_theme(),
            "login_monthly_theme": get_login_monthly_theme(),
        }

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
