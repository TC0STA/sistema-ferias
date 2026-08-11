"""Persistência isolada dos usuários do sistema."""

from __future__ import annotations

import sqlite3
import re
from contextlib import closing
from datetime import datetime
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

from models.user import User


VALID_PROFILES = frozenset({"admin", "rh", "gestor", "consulta"})
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.fullmatch(email.strip()))


class UserService:
    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._schema_ready = False

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def ensure_schema(self) -> bool:
        """Garante o schema e informa se um novo arquivo foi criado."""
        if self._schema_ready:
            return False

        database_path = Path(self.database_path)
        database_exists = database_path.exists()
        database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            if database_exists:
                table_exists = connection.execute(
                    """
                    SELECT 1 FROM sqlite_master
                    WHERE type = 'table' AND name = 'usuarios'
                    """
                ).fetchone()
                if table_exists is None:
                    raise RuntimeError(
                        "O banco de usuários existente não contém a tabela "
                        "usuarios; a inicialização foi interrompida."
                    )
                self._schema_ready = True
                return False

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
        return True

    def initialize(self) -> bool:
        """Inicializa o serviço sem repovoar bancos existentes vazios."""
        database_created = self.ensure_schema()
        if database_created:
            self.create(
                nome="Administrador",
                usuario="admin",
                email="admin@fokus.local",
                senha="admin123",
                perfil="admin"
            )
            return True

        if self.count() == 0:
            raise RuntimeError(
                "O banco de usuários existente está vazio. "
                "O administrador padrão não será recriado automaticamente."
            )
        return False

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
        if not is_valid_email(email):
            raise ValueError("Informe um e-mail válido.")
        if len(senha) < 8:
            raise ValueError("A senha deve ter no mínimo 8 caracteres.")

        self.ensure_schema()
        created_at = datetime.now().isoformat(timespec="seconds")
        try:
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
        except sqlite3.IntegrityError as error:
            message = str(error).lower()
            if "email" in message:
                raise ValueError("Este e-mail já está cadastrado.") from error
            if "usuario" in message:
                raise ValueError("Este usuário já está cadastrado.") from error
            raise ValueError("Não foi possível cadastrar o usuário.") from error
        return self.get_by_id(user_id)

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

    def get_by_email(self, email: str) -> User | None:
        self.ensure_schema()
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT * FROM usuarios WHERE email = ? COLLATE NOCASE",
                (email.strip(),)
            ).fetchone()
        return User.from_row(row) if row else None

    def list_all(self) -> list[User]:
        self.ensure_schema()
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM usuarios ORDER BY ativo DESC, nome COLLATE NOCASE"
            ).fetchall()
        return [User.from_row(row) for row in rows]

    def update(
        self,
        user_id: int,
        *,
        nome: str,
        email: str,
        perfil: str,
        ativo: bool
    ) -> User:
        self.ensure_schema()
        if not nome.strip():
            raise ValueError("O nome é obrigatório.")
        if not is_valid_email(email):
            raise ValueError("Informe um e-mail válido.")
        if perfil not in VALID_PROFILES:
            raise ValueError("Perfil de usuário inválido.")
        try:
            with closing(self._connect()) as connection:
                cursor = connection.execute(
                    """
                    UPDATE usuarios
                    SET nome = ?, email = ?, perfil = ?, ativo = ?
                    WHERE id = ?
                    """,
                    (nome.strip(), email.strip(), perfil, int(ativo), user_id)
                )
                connection.commit()
        except sqlite3.IntegrityError as error:
            if "email" in str(error).lower():
                raise ValueError("Este e-mail já está cadastrado.") from error
            raise ValueError("Não foi possível atualizar o usuário.") from error
        if cursor.rowcount == 0:
            raise ValueError("Usuário não encontrado.")
        return self.get_by_id(user_id)

    def set_active(self, user_id: int, active: bool) -> User:
        self.ensure_schema()
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE usuarios SET ativo = ? WHERE id = ?",
                (int(active), user_id)
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise ValueError("Usuário não encontrado.")
        return self.get_by_id(user_id)

    def reset_password(self, user_id: int, new_password: str) -> User:
        self.ensure_schema()
        if len(new_password) < 8:
            raise ValueError("A senha deve ter no mínimo 8 caracteres.")
        password_hash = generate_password_hash(new_password)
        with closing(self._connect()) as connection:
            cursor = connection.execute(
                "UPDATE usuarios SET senha_hash = ? WHERE id = ?",
                (password_hash, user_id)
            )
            connection.commit()
        if cursor.rowcount == 0:
            raise ValueError("Usuário não encontrado.")
        return self.get_by_id(user_id)

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
