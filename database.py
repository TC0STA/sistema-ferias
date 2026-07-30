import sqlite3
from pathlib import Path

DATABASE_PATH = Path(__file__).resolve().parent / "database" / "ferias.db"

def criar_banco():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bloqueios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        data_bloqueio DATE,
        data_execucao DATETIME
    )
    """)

    conn.commit()
    conn.close()
