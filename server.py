"""
server.py — API Bloom Filter demo
Architecture résiliente :
  - Support PostgreSQL (Docker) avec bascule transparente vers SQLite (bloom.db) si PostgreSQL est hors-ligne.
  - Rechargement automatique et paginé du filtre lors d'une reconfiguration (évite le vidage du filtre).
  - Mesure précise des performances en direct (temps Bloom en microsecondes vs temps DB en millisecondes).
  - Auto-initialisation depuis dataset/users_sample.csv si la base est vide.
"""

from __future__ import annotations
import math
import hashlib
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    import psycopg
    from psycopg_pool import ConnectionPool
    PSYCOPG_AVAILABLE = True
except ImportError:
    PSYCOPG_AVAILABLE = False
    ConnectionPool = None


# ── Bloom Filter ──────────────────────────────────────────────────────────────

class BloomFilter:
    def __init__(self, capacity: int = 1000, false_positive_rate: float = 0.01):
        self._lock = threading.RLock()
        self._build(capacity, false_positive_rate, None)

    def _build(self, capacity: int, false_positive_rate: float, k_override: int | None):
        self.capacity = capacity
        self.false_positive_rate = false_positive_rate
        self.m = math.ceil(-capacity * math.log(false_positive_rate) / (math.log(2) ** 2))
        k_optimal = max(1, round((self.m / capacity) * math.log(2)))
        self.k = k_override if k_override and k_override > 0 else k_optimal
        self.k_optimal = k_optimal
        self.bits = bytearray((self.m + 7) // 8)
        self._count = 0

    def reconfigure(self, capacity: int, false_positive_rate: float, k_override: int | None):
        with self._lock:
            self._build(capacity, false_positive_rate, k_override)

    def reset_bits(self):
        with self._lock:
            self.bits = bytearray((self.m + 7) // 8)
            self._count = 0

    def _positions(self, item: str) -> list[int]:
        data = item.encode("utf-8")
        digest = hashlib.blake2b(data, digest_size=16).digest()
        h1 = int.from_bytes(digest[:8], "big")
        h2 = int.from_bytes(digest[8:], "big") | 1  # h2 impair pour coprimalité
        return [(h1 + i * h2) % self.m for i in range(self.k)]

    def _h1_h2(self, item: str) -> tuple[int, int]:
        data = item.encode("utf-8")
        digest = hashlib.blake2b(data, digest_size=16).digest()
        h1 = int.from_bytes(digest[:8], "big")
        h2 = int.from_bytes(digest[8:], "big") | 1
        return h1, h2

    def add(self, item: str):
        with self._lock:
            for pos in self._positions(item):
                self.bits[pos // 8] |= 1 << (pos % 8)
            self._count += 1

    def might_contain(self, item: str) -> bool:
        with self._lock:
            for pos in self._positions(item):
                if (self.bits[pos // 8] & (1 << (pos % 8))) == 0:
                    return False
            return True

    def bit_is_set(self, pos: int) -> bool:
        with self._lock:
            if pos < 0 or pos >= self.m:
                return False
            return bool(self.bits[pos // 8] & (1 << (pos % 8)))

    @property
    def inserted_count(self):
        return self._count

    def bits_on_count(self) -> int:
        with self._lock:
            total = 0
            for byte in self.bits:
                total += bin(byte).count("1")
            return total

    def stats(self) -> dict:
        bits_on = self.bits_on_count()
        saturation = (bits_on / self.m) * 100 if self.m > 0 else 0
        return {
            "capacity": self.capacity,
            "false_positive_rate": self.false_positive_rate,
            "m": self.m,
            "k": self.k,
            "k_optimal": self.k_optimal,
            "inserted_count": self._count,
            "bits_on": bits_on,
            "saturation_pct": round(saturation, 2),
            "memory_bytes": len(self.bits),
        }


# ── Database Layer (PostgreSQL ou SQLite) ─────────────────────────────────────

PG_DSN = os.getenv("PG_DSN", "host=localhost port=5432 dbname=bloomdb user=bloom password=bloom")
SQLITE_PATH = os.getenv("SQLITE_PATH", "bloom.db")
SAMPLE_CSV = "dataset/users_sample.csv"

db_engine = "none"  # "postgres" ou "sqlite"
pg_pool = None
sqlite_lock = threading.Lock()


def init_db_connection() -> str:
    """Tente d'ouvrir PostgreSQL, sinon bascule vers SQLite."""
    global db_engine, pg_pool

    # 1. Tester rapidement PostgreSQL (1 seconde max)
    if PSYCOPG_AVAILABLE:
        try:
            test_conn = psycopg.connect(PG_DSN, connect_timeout=1)
            test_conn.close()
            pool = ConnectionPool(PG_DSN, min_size=1, max_size=8, open=False)
            pool.open(timeout=2.0)
            with pool.connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS items (
                        id SERIAL PRIMARY KEY,
                        value TEXT UNIQUE NOT NULL,
                        inserted_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_items_value ON items(value);
                """)
            pg_pool = pool
            db_engine = "postgres"
            print("[database] Connecté à PostgreSQL (Docker)")
            return "postgres"
        except Exception as e:
            print(f"[database] PostgreSQL indisponible. Bascule vers SQLite local.")

    # 2. Utiliser SQLite local
    with sqlite_lock:
        conn = sqlite3.connect(SQLITE_PATH)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                value TEXT UNIQUE NOT NULL,
                inserted_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_items_value ON items(value);")
        conn.commit()
        conn.close()

    db_engine = "sqlite"
    print(f"[database] Connecté à SQLite local ({SQLITE_PATH})")
    return "sqlite"


def count_db_items() -> int:
    """Retourne le nombre total d'items dans la base."""
    if db_engine == "postgres" and pg_pool:
        try:
            with pg_pool.connection() as conn:
                res = conn.execute("SELECT COUNT(*) FROM items").fetchone()
                return res[0] if res else 0
        except Exception:
            return 0
    else:
        with sqlite_lock:
            conn = sqlite3.connect(SQLITE_PATH)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM items")
            res = cur.fetchone()
            conn.close()
            return res[0] if res else 0


def db_has_item(value: str) -> bool:
    """Vérifie l'existence exacte de la valeur dans la DB."""
    if db_engine == "postgres" and pg_pool:
        with pg_pool.connection() as conn:
            return conn.execute("SELECT 1 FROM items WHERE value = %s", (value,)).fetchone() is not None
    else:
        with sqlite_lock:
            conn = sqlite3.connect(SQLITE_PATH)
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM items WHERE value = ? LIMIT 1", (value,))
            found = cur.fetchone() is not None
            conn.close()
            return found


def db_insert_item(value: str) -> bool:
    """Insère un item s'il n'existe pas déjà. Renvoie True si inséré, False si doublon."""
    if db_engine == "postgres" and pg_pool:
        with pg_pool.connection() as conn:
            cur = conn.execute("INSERT INTO items(value) VALUES (%s) ON CONFLICT DO NOTHING", (value,))
            return cur.rowcount > 0
    else:
        with sqlite_lock:
            conn = sqlite3.connect(SQLITE_PATH)
            cur = conn.cursor()
            cur.execute("INSERT OR IGNORE INTO items(value) VALUES (?)", (value,))
            inserted = cur.rowcount > 0
            conn.commit()
            conn.close()
            return inserted


def db_truncate_items():
    """Vide la table items."""
    if db_engine == "postgres" and pg_pool:
        with pg_pool.connection() as conn:
            conn.execute("TRUNCATE items RESTART IDENTITY")
    else:
        with sqlite_lock:
            conn = sqlite3.connect(SQLITE_PATH)
            conn.execute("DELETE FROM items")
            conn.commit()
            conn.close()


def auto_seed_if_empty(target_count: int = 1000):
    """Si la base est vide, peuple automatiquement depuis dataset/users_sample.csv en batch rapide."""
    current_count = count_db_items()
    if current_count > 0:
        return

    if not os.path.exists(SAMPLE_CSV):
        return

    print(f"[seed] Base vide détectée. Auto-chargement de {target_count} pseudos depuis {SAMPLE_CSV}...")
    import csv
    usernames = []
    with open(SAMPLE_CSV, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        col = "username" if "username" in (reader.fieldnames or []) else (reader.fieldnames[0] if reader.fieldnames else None)
        if col:
            for row in reader:
                val = (row.get(col) or "").strip()
                if val:
                    usernames.append(val)
                if len(usernames) >= target_count:
                    break

    if db_engine == "postgres" and pg_pool:
        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO items(value) VALUES (%s) ON CONFLICT DO NOTHING",
                    [(u,) for u in usernames]
                )
            conn.commit()
    else:
        with sqlite_lock:
            conn = sqlite3.connect(SQLITE_PATH)
            conn.executemany(
                "INSERT OR IGNORE INTO items(value) VALUES (?)",
                [(u,) for u in usernames]
            )
            conn.commit()
            conn.close()

    print(f"[seed] Auto-chargement terminé : {len(usernames)} items ajoutés en DB.")


def rebuild_bloom_from_db():
    """Recharge paginé du Bloom filter depuis la base de données."""
    bloom.reset_bits()
    loaded = 0

    if db_engine == "postgres" and pg_pool:
        with pg_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT value FROM items")
                while rows := cur.fetchmany(5000):
                    for (val,) in rows:
                        bloom.add(val)
                        loaded += 1
    else:
        with sqlite_lock:
            conn = sqlite3.connect(SQLITE_PATH)
            cur = conn.cursor()
            cur.execute("SELECT value FROM items")
            while rows := cur.fetchmany(5000):
                for (val,) in rows:
                    bloom.add(val)
                    loaded += 1
            conn.close()

    print(f"[bloom] Filtre reconstruit depuis la DB ({db_engine}) : {loaded} items chargés.")
    return loaded


# ── Global instances ──────────────────────────────────────────────────────────

bloom = BloomFilter(capacity=1000, false_positive_rate=0.01)


# ── Lifespan & Initialization ───────────────────────────────────────────────

def ensure_initialized():
    """Initialise la connexion DB et le filtre si pas encore fait."""
    global db_engine
    if db_engine == "none":
        init_db_connection()
        auto_seed_if_empty(target_count=1000)
        rebuild_bloom_from_db()

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_initialized()
    yield
    if pg_pool:
        try:
            pg_pool.close()
        except Exception:
            pass


# ── FastAPI App ───────────────────────────────────────────────────────────────

app = FastAPI(title="Bloom Filter Live API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Request Models ────────────────────────────────────────────────────────────

class ConfigBody(BaseModel):
    capacity: int = 1000
    false_positive_rate: float = 0.01
    k_override: int | None = None

class InsertBody(BaseModel):
    text: str

class CheckBody(BaseModel):
    text: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.post("/configure")
def configure(body: ConfigBody):
    """Reconfigure la taille et les fonctions de hachage, puis recharge les éléments existants."""
    ensure_initialized()
    bloom.reconfigure(body.capacity, body.false_positive_rate, body.k_override)
    rebuild_bloom_from_db()
    return {
        "ok": True,
        "engine": db_engine,
        "db_count": count_db_items(),
        "stats": bloom.stats()
    }


@app.get("/hashes")
def hashes(text: str):
    """Génère les composantes de hachage BLAKE2b réelles et la décomposition double hashing."""
    ensure_initialized()
    if not text:
        return {"positions": [], "h1": 0, "h2": 0, "steps": [], "m": bloom.m, "k": bloom.k}

    h1, h2 = bloom._h1_h2(text)
    positions = bloom._positions(text)
    steps = [
        {
            "i": i,
            "pos": (h1 + i * h2) % bloom.m,
            "calc": f"({h1} + {i} × {h2}) mod {bloom.m}"
        }
        for i in range(bloom.k)
    ]
    return {
        "text": text,
        "h1": str(h1),
        "h2": str(h2),
        "m": bloom.m,
        "k": bloom.k,
        "positions": positions,
        "steps": steps,
        "bits_set": [bloom.bit_is_set(p) for p in positions],
    }


@app.post("/check")
def check(body: CheckBody):
    """
    Vérification de présence avec mesure directe du temps Bloom vs temps DB.
    Si le Bloom Filter répond absent, la requête SQL est totalement évitée.
    """
    ensure_initialized()
    text = body.text.strip()
    if not text:
        return {"text": "", "bloom": False, "in_db": False, "verdict": "idle"}

    # 1. Évaluation Bloom Filter en RAM (chronométrée en nanosecondes)
    t0 = time.perf_counter_ns()
    bloom_hit = bloom.might_contain(text)
    bloom_duration_ns = time.perf_counter_ns() - t0

    bloom_us = round(bloom_duration_ns / 1_000, 3)

    # 2. Si Bloom dit absent -> ÉCONOMIE TOTALE DE REQUÊTE DB (zéro faux négatif)
    if not bloom_hit:
        return {
            "text": text,
            "bloom": False,
            "in_db": False,
            "verdict": "absent",
            "timing": {
                "bloom_us": bloom_us,
                "db_ms": 0.0,
                "db_avoided": True,
                "engine": db_engine,
            }
        }

    # 3. Si Bloom dit "peut-être présent" -> Vérification obligatoire en DB
    t1 = time.perf_counter_ns()
    in_db = db_has_item(text)
    db_duration_ns = time.perf_counter_ns() - t1
    db_ms = round(db_duration_ns / 1_000_000, 3)

    verdict = "confirmed" if in_db else "false_positive"

    return {
        "text": text,
        "bloom": True,
        "in_db": in_db,
        "verdict": verdict,
        "timing": {
            "bloom_us": bloom_us,
            "db_ms": db_ms,
            "db_avoided": False,
            "engine": db_engine,
        }
    }


@app.post("/insert")
def insert(body: InsertBody):
    """Insère un texte dans la base et dans le Bloom filter."""
    ensure_initialized()
    text = body.text.strip()
    if not text:
        return JSONResponse({"error": "Texte vide"}, 400)

    bloom_hit = bloom.might_contain(text)
    inserted = db_insert_item(text)
    bloom.add(text)

    status = "inserted" if inserted else "duplicate"
    return {
        "text": text,
        "status": status,
        "bloom_said": bloom_hit,
        "false_positive": bloom_hit and not inserted,
        "engine": db_engine,
        "stats": bloom.stats()
    }


@app.get("/state")
def state(max_bits: int = 256):
    """Retourne l'état du bit array, les stats du filtre et l'état de la base."""
    ensure_initialized()
    bits_sample = [bloom.bit_is_set(i) for i in range(min(max_bits, bloom.m))]
    return {
        "engine": db_engine,
        "db_item_count": count_db_items(),
        "bits": bits_sample,
        "stats": bloom.stats()
    }


@app.delete("/reset")
def reset():
    """Vide à la fois le Bloom Filter et la base de données."""
    ensure_initialized()
    db_truncate_items()
    bloom.reset_bits()
    return {"ok": True, "engine": db_engine, "stats": bloom.stats()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
