"""Migra usuarios.db para PostgreSQL sem alterar o arquivo de origem."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from services.user_service import UserService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Migra todos os usuários do SQLite para um PostgreSQL vazio."
    )
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=BASE_DIR / "database" / "usuarios.db",
        help="Caminho do usuarios.db de origem.",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        parser.error("Defina DATABASE_URL somente no ambiente antes da migração.")

    service = UserService(database_url)
    migrated = service.migrate_from_sqlite(args.sqlite)
    print(
        f"Migração concluída: {migrated} usuário(s) copiado(s) para PostgreSQL."
    )
    print("O arquivo SQLite foi mantido sem alterações como backup temporário.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
