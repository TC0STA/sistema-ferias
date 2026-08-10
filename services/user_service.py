"""Persistência isolada dos usuários do sistema."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from models.user import User


VALID_PROFILES = frozenset({"admin", "rh", "gestor", "consulta"})


class UserService:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._schema_ready = False

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    usuario TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    senha_hash TEXT NOT NULL,
                    perfil TEXT NOT NULL CHECK (
                        perfil IN ('admin', 'rh', 'gestor', 'consulta')
                    ),
                    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
                    ultimo_login TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            connection.commit()
        self._schema_ready = True

    def count(self) -> int:
        self.ensure_schema()
        with closing(self._connect()) as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM usuarios"
            ).fetchone()[0])

    def create(
        self,
        *,
        nome: str,
        usuario: str,
        email: str,
        senha: str,
        perfil: str,
        ativo: bool = True
    ) -> User:
        if perfil not in VALID_PROFILES:
            raise ValueError("Perfil de usuário inválido.")
        if not nome.strip() or not usuario.strip() or not senha:
            raise ValueError("Nome, usuário e senha são obrigatórios.")

        self.ensure_schema()
        created_at = datetime.now().isoformat(timespec="seconds")
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                """
                INSERT INTO usuarios (
                    nome, usuario, email, senha_hash, perfil, ativo, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    nome.strip(), usuario.strip(), email.strip(),
                    generate_password_hash(senha), perfil,
                    int(ativo), created_at
                )
            )
            user_id = cursor.lastrowid
            connection.commit()
        return self.get_by_id(user_id)

    def ensure_default_admin(self) -> bool:
        if self.count() > 0:
            return False
        self.create(
            nome="Administrador",
            usuario="admin",
            email="admin@fokus.local",
            senha="admin123",
            perfil="admin"
        )
        return True

    def get_by_id(self, user_id: int) -> User | None:
        self.ensure_schema()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM usuarios WHERE id = ?",
                (user_id,)
            ).fetchone()
        return User.from_row(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        self.ensure_schema()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM usuarios WHERE usuario = ? COLLATE NOCASE",
                (username.strip(),)
            ).fetchone()
        return User.from_row(row) if row else None

    def update_last_login(self, user_id: int) -> datetime:
        moment = datetime.now()
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE usuarios SET ultimo_login = ? WHERE id = ?",
                (moment.isoformat(timespec="seconds"), user_id)
            )
            connection.commit()
        return moment

    def change_password(
        self,
        user_id: int,
        current_password: str,
        new_password: str
    ) -> bool:
        """Troca a senha após validar a atual, persistindo somente o hash."""
        if len(new_password) < 8:
            return False

        user = self.get_by_id(user_id)
        if user is None or not check_password_hash(
            user.senha_hash, current_password
        ):
            return False

        password_hash = generate_password_hash(new_password)
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE usuarios SET senha_hash = ? WHERE id = ?",
                (password_hash, user_id)
            )
            connection.commit()
        return True
