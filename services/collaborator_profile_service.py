"""Persistência isolada dos ajustes locais de colaboradores."""

from __future__ import annotations

import sqlite3
import unicodedata
import uuid
from contextlib import closing
from datetime import datetime
from pathlib import Path


def normalizar_identidade(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join(
        "".join(char for char in text if not unicodedata.combining(char))
        .lower()
        .split()
    )


class CollaboratorProfileService:
    """Mantém perfis locais identificados por proprietário e colaborador."""

    TABLE = "colaborador_perfis"
    REQUIRED_COLUMNS = {
        "id", "usuario_id", "colaborador_chave", "nome", "departamento",
        "cargo", "matricula", "filial", "atualizado_em",
    }

    def __init__(self, database_path: str, backup_root: str):
        self.database_path = str(database_path)
        self.backup_root = Path(backup_root)
        self.last_backup: str | None = None

    @staticmethod
    def _columns(conn) -> set[str]:
        return {
            str(row[1])
            for row in conn.execute(
                "PRAGMA table_info(colaborador_perfis)"
            ).fetchall()
        }

    @staticmethod
    def _create_table(conn, table: str = TABLE) -> None:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario_id INTEGER,
                colaborador_chave TEXT NOT NULL,
                nome TEXT NOT NULL,
                departamento TEXT,
                cargo TEXT,
                matricula TEXT,
                filial TEXT,
                atualizado_em TEXT
            )
        """)

    @staticmethod
    def _create_indexes(conn) -> None:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS colaborador_perfis_usuario_id_idx "
            "ON colaborador_perfis (usuario_id)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "colaborador_perfis_escopo_chave_uidx "
            "ON colaborador_perfis (COALESCE(usuario_id, -1), colaborador_chave)"
        )

    def _backup_database(self) -> str:
        destination_dir = self.backup_root / "migracoes" / "colaborador_perfis"
        destination_dir.mkdir(parents=True, exist_ok=True)
        moment = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        destination = destination_dir / (
            f"ferias_antes_colaborador_perfis_{moment}_{uuid.uuid4().hex[:8]}.db"
        )
        with closing(sqlite3.connect(self.database_path)) as source:
            with closing(sqlite3.connect(destination)) as target:
                source.backup(target)
        self.last_backup = str(destination)
        return self.last_backup

    def _migrate_legacy_table(self) -> None:
        self._backup_database()
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.row_factory = sqlite3.Row
            try:
                conn.execute("BEGIN IMMEDIATE")
                rows = conn.execute(
                    "SELECT nome, departamento, cargo, matricula, filial, "
                    "atualizado_em FROM colaborador_perfis ORDER BY nome"
                ).fetchall()
                temporary = "colaborador_perfis_migracao"
                conn.execute(f"DROP TABLE IF EXISTS {temporary}")
                self._create_table(conn, temporary)

                used_keys: set[str] = set()
                for index, row in enumerate(rows, start=1):
                    base_key = f"nome:{normalizar_identidade(row['nome'])}"
                    key = base_key
                    if key in used_keys:
                        key = f"{base_key}:legado:{index}"
                    used_keys.add(key)
                    conn.execute(f"""
                        INSERT INTO {temporary} (
                            usuario_id, colaborador_chave, nome, departamento,
                            cargo, matricula, filial, atualizado_em
                        ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        key, row["nome"], row["departamento"], row["cargo"],
                        row["matricula"], row["filial"], row["atualizado_em"],
                    ))

                migrated = conn.execute(
                    f"SELECT COUNT(*) FROM {temporary}"
                ).fetchone()[0]
                if migrated != len(rows):
                    raise RuntimeError(
                        "A migração de colaborador_perfis perdeu registros."
                    )
                conn.execute("DROP TABLE colaborador_perfis")
                conn.execute(
                    f"ALTER TABLE {temporary} RENAME TO colaborador_perfis"
                )
                self._create_indexes(conn)
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def ensure_schema(self) -> None:
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.database_path)) as conn:
            columns = self._columns(conn)
            if not columns:
                self._create_table(conn)
                self._create_indexes(conn)
                conn.commit()
                return
            if self.REQUIRED_COLUMNS.issubset(columns):
                self._create_indexes(conn)
                conn.commit()
                return

        self._migrate_legacy_table()

    @staticmethod
    def _to_dict(row) -> dict | None:
        return dict(row) if row is not None else None

    def get(
        self, *, usuario_id: int | None, colaborador_chave: str, nome: str
    ) -> dict | None:
        self.ensure_schema()
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM colaborador_perfis "
                "WHERE usuario_id IS ? AND colaborador_chave = ?",
                (usuario_id, colaborador_chave),
            ).fetchone()
            if row is not None or usuario_id is not None:
                return self._to_dict(row)

            legacy = [
                item for item in conn.execute(
                    "SELECT * FROM colaborador_perfis WHERE usuario_id IS NULL"
                ).fetchall()
                if normalizar_identidade(item["nome"])
                == normalizar_identidade(nome)
            ]
            return self._to_dict(legacy[0]) if len(legacy) == 1 else None

    def list_legacy_by_name(self) -> dict[str, dict]:
        """Compatibilidade dos módulos ainda não migrados para o novo escopo."""
        self.ensure_schema()
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM colaborador_perfis WHERE usuario_id IS NULL"
            ).fetchall()
        return {
            normalizar_identidade(row["nome"]): dict(row)
            for row in rows
        }

    def save(
        self,
        *,
        usuario_id: int | None,
        colaborador_chave: str,
        nome: str,
        departamento: str,
        cargo: str,
        matricula: str,
        filial: str,
    ) -> None:
        self.ensure_schema()
        now = datetime.now().isoformat()
        with closing(sqlite3.connect(self.database_path)) as conn:
            conn.row_factory = sqlite3.Row
            existing = conn.execute(
                "SELECT id FROM colaborador_perfis "
                "WHERE usuario_id IS ? AND colaborador_chave = ?",
                (usuario_id, colaborador_chave),
            ).fetchone()
            if existing is None and usuario_id is None:
                matches = [
                    row for row in conn.execute(
                        "SELECT id, nome FROM colaborador_perfis "
                        "WHERE usuario_id IS NULL"
                    ).fetchall()
                    if normalizar_identidade(row["nome"])
                    == normalizar_identidade(nome)
                ]
                if len(matches) == 1:
                    existing = matches[0]

            if existing is None:
                conn.execute("""
                    INSERT INTO colaborador_perfis (
                        usuario_id, colaborador_chave, nome, departamento,
                        cargo, matricula, filial, atualizado_em
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    usuario_id, colaborador_chave, nome, departamento, cargo,
                    matricula, filial, now,
                ))
            else:
                conn.execute("""
                    UPDATE colaborador_perfis
                    SET colaborador_chave = ?, nome = ?, departamento = ?,
                        cargo = ?, matricula = ?, filial = ?, atualizado_em = ?
                    WHERE id = ?
                """, (
                    colaborador_chave, nome, departamento, cargo, matricula,
                    filial, now, existing["id"],
                ))
            conn.commit()


__all__ = ["CollaboratorProfileService", "normalizar_identidade"]
