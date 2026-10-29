"""
seed.py — Charge un échantillon de dataset/users.csv ou dataset/users_sample.csv dans la base de données.
Supporte automatiquement PostgreSQL (Docker) avec bascule transparente vers SQLite (local) si Docker n'est pas lancé.

Usage :
    python seed.py                     # Insère 1000 items (par défaut) dans la DB
    python seed.py --limit 2500        # Insère 2500 items
    python seed.py --limit 0           # Insère tous les items du fichier
    python seed.py --db sqlite         # Force l'utilisation de SQLite (bloom.db)
    python seed.py --file dataset/users.csv  # Spécifie un autre fichier CSV
"""

from __future__ import annotations
import argparse
import csv
import os
import sqlite3
import sys
import time

PG_DSN = os.getenv("PG_DSN", "host=localhost port=5432 dbname=bloomdb user=bloom password=bloom")
SQLITE_DB = os.getenv("SQLITE_PATH", "bloom.db")
DEFAULT_SAMPLE = "dataset/users_sample.csv"
DEFAULT_RAW = "dataset/users.csv"


def get_csv_path(user_path: str | None) -> str:
    if user_path and os.path.exists(user_path):
        return user_path
    if os.path.exists(DEFAULT_SAMPLE):
        return DEFAULT_SAMPLE
    if os.path.exists(DEFAULT_RAW):
        return DEFAULT_RAW
    raise FileNotFoundError("Aucun fichier CSV trouvé dans dataset/ (users_sample.csv ou users.csv)")


def read_usernames(csv_path: str, limit: int | None = None) -> list[str]:
    """Lit les usernames depuis le fichier CSV avec détection automatique de la colonne."""
    usernames = []
    seen = set()

    with open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        col = None
        if reader.fieldnames:
            if "username" in reader.fieldnames:
                col = "username"
            elif "author" in reader.fieldnames:
                col = "author"
            elif "value" in reader.fieldnames:
                col = "value"
            else:
                col = reader.fieldnames[0]

        for row in reader:
            val = (row.get(col) or "").strip()
            if not val or val in seen:
                continue
            seen.add(val)
            usernames.append(val)
            if limit and limit > 0 and len(usernames) >= limit:
                break

    return usernames


def try_postgres(usernames: list[str]) -> bool:
    """Tente d'insérer dans PostgreSQL si disponible."""
    try:
        import psycopg
    except ImportError:
        return False

    try:
        with psycopg.connect(PG_DSN, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS items (
                        id SERIAL PRIMARY KEY,
                        value TEXT UNIQUE NOT NULL,
                        inserted_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_items_value ON items(value);
                """)
                batch_size = 1000
                total_inserted = 0
                for i in range(0, len(usernames), batch_size):
                    batch = [(u,) for u in usernames[i : i + batch_size]]
                    cur.executemany(
                        "INSERT INTO items(value) VALUES (%s) ON CONFLICT DO NOTHING",
                        batch
                    )
                    total_inserted += cur.rowcount
                conn.commit()
                cur.execute("SELECT COUNT(*) FROM items")
                db_total = cur.fetchone()[0]
                print(f"[seed:PostgreSQL] {total_inserted} items insérés ({db_total} total en DB)")
        return True
    except Exception as e:
        print(f"[seed:PostgreSQL] Connexion impossible ({e})")
        return False


def seed_sqlite(usernames: list[str], db_path: str):
    """Insère dans la base locale SQLite."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            value TEXT UNIQUE NOT NULL,
            inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_items_value ON items(value);")

    batch_size = 1000
    total_inserted = 0
    for i in range(0, len(usernames), batch_size):
        batch = [(u,) for u in usernames[i : i + batch_size]]
        cur.executemany("INSERT OR IGNORE INTO items(value) VALUES (?)", batch)
        total_inserted += cur.rowcount
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM items")
    db_total = cur.fetchone()[0]
    conn.close()
    print(f"[seed:SQLite] {total_inserted} items insérés dans '{db_path}' ({db_total} total en DB)")


def main():
    parser = argparse.ArgumentParser(description="Seed database for Bloom Filter demo")
    parser.add_argument("--file", "-f", type=str, default=None, help="Chemin du CSV")
    parser.add_argument("--limit", "-n", type=int, default=1000, help="Nombre max d'items (0 = tout)")
    parser.add_argument("--db", choices=["auto", "postgres", "sqlite"], default="auto", help="Moteur DB")
    args = parser.parse_args()

    csv_file = get_csv_path(args.file)
    print(f"[seed] Lecture depuis {csv_file} (limite = {args.limit if args.limit > 0 else 'toutes'})...")
    t0 = time.perf_counter()
    usernames = read_usernames(csv_file, args.limit)
    print(f"[seed] {len(usernames)} usernames chargés depuis le fichier en {time.perf_counter() - t0:.2f}s")

    if args.db == "postgres":
        if not try_postgres(usernames):
            print("[seed] Échec avec PostgreSQL.", file=sys.stderr)
            sys.exit(1)
    elif args.db == "sqlite":
        seed_sqlite(usernames, SQLITE_DB)
    else:  # auto
        if not try_postgres(usernames):
            print("[seed] Bascule automatique vers SQLite...")
            seed_sqlite(usernames, SQLITE_DB)


if __name__ == "__main__":
    main()
