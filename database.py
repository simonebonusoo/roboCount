"""
Strato dati di Monitor Spese su PostgreSQL (Supabase).

Storicamente l'app usava SQLite. Per ottenere un database persistente e
gratuito in produzione siamo passati a PostgreSQL (Supabase), MA senza
riscrivere le ~146 query sparse in services.py: questo modulo fa da
"adattatore".

get_connection() restituisce un oggetto che espone la stessa interfaccia di
sqlite3 usata dal resto del codice:
  - connection.execute("... ?", (a, b))   -> i placeholder '?' vengono
    tradotti nei '%s' di psycopg;
  - le righe sono accessibili per nome (row["colonna"]) e per indice (row[0]);
  - cursor.lastrowid funziona (via SELECT lastval());
  - "with get_connection() as c:" fa commit in uscita (rollback in caso di
    errore) e chiude la connessione.

La connessione viene letta dalla variabile d'ambiente DATABASE_URL (stringa
di connessione PostgreSQL di Supabase, meglio il pooler in modalita
transaction, porta 6543).
"""

from __future__ import annotations

import os
import re

import psycopg
from psycopg.rows import tuple_row
from psycopg_pool import ConnectionPool


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


# ---------------------------------------------------------------------------
# Riga compatibile con sqlite3.Row: accesso per nome E per indice numerico.
# ---------------------------------------------------------------------------
class Row(dict):
    def __init__(self, columns, values):
        super().__init__(zip(columns, values))
        self._values = tuple(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return dict.__getitem__(self, key)


def _row_factory(cursor):
    columns = [col.name for col in cursor.description] if cursor.description else []

    def make(values):
        return Row(columns, values)

    return make


# ---------------------------------------------------------------------------
# Traduzione dal dialetto SQLite a PostgreSQL.
# Nel codice non ci sono '%' o 'LIKE' nelle query, ne '?' dentro le stringhe:
# la sostituzione '?' -> '%s' e quindi sicura (verificato).
# ---------------------------------------------------------------------------
_INSERT_OR_IGNORE_RE = re.compile(r"INSERT\s+OR\s+IGNORE\s+INTO", re.IGNORECASE)


def _translate(sql: str) -> str:
    translated = sql
    if _INSERT_OR_IGNORE_RE.search(translated):
        # SQLite: "INSERT OR IGNORE" -> PostgreSQL: "INSERT ... ON CONFLICT DO NOTHING"
        translated = _INSERT_OR_IGNORE_RE.sub("INSERT INTO", translated)
        translated = translated.rstrip().rstrip(";")
        translated = translated + "\nON CONFLICT DO NOTHING"
    return translated.replace("?", "%s")


class _Cursor:
    """Avvolge un cursore psycopg per offrire l'API usata dal codice SQLite."""

    def __init__(self, cursor, connection):
        self._cursor = cursor
        self._connection = connection

    def execute(self, sql, params=None):
        # Necessario per pandas.read_sql_query, che chiama cursor.execute().
        self._cursor.execute(_translate(sql), tuple(params) if params else None)
        return self

    def executemany(self, sql, seq_of_params):
        self._cursor.executemany(_translate(sql), [tuple(p) for p in seq_of_params])
        return self

    def fetchone(self):
        return self._cursor.fetchone()

    def fetchall(self):
        return self._cursor.fetchall()

    def __iter__(self):
        return iter(self._cursor)

    @property
    def description(self):
        return self._cursor.description

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()

    @property
    def lastrowid(self):
        # Equivalente di sqlite3 cursor.lastrowid: l'ultimo valore di sequenza
        # generato nella sessione corrente (stessa transazione dell'INSERT).
        with self._connection.raw.cursor() as helper:
            helper.execute("SELECT lastval()")
            return helper.fetchone()[0]


class Connection:
    """Avvolge una connessione psycopg replicando l'interfaccia di sqlite3."""

    def __init__(self, raw, pool=None):
        self.raw = raw
        self._pool = pool

    def _release(self):
        # Restituisce la connessione al pool (o la chiude se non c'e pool).
        if self._pool is not None:
            self._pool.putconn(self.raw)
        else:
            self.raw.close()

    def execute(self, sql, params=None):
        cursor = self.raw.cursor()
        cursor.execute(_translate(sql), tuple(params) if params else None)
        return _Cursor(cursor, self)

    def executemany(self, sql, seq_of_params):
        cursor = self.raw.cursor()
        cursor.executemany(_translate(sql), [tuple(p) for p in seq_of_params])
        return _Cursor(cursor, self)

    def cursor(self):
        # Usato solo da pandas.read_sql_query, che si aspetta righe come tuple
        # semplici (non le nostre righe con accesso per nome).
        return _Cursor(self.raw.cursor(row_factory=tuple_row), self)

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()

    def close(self):
        self._release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.raw.commit()
            else:
                self.raw.rollback()
        finally:
            self._release()
        return False


# ---------------------------------------------------------------------------
# Pool di connessioni: riusa le connessioni invece di aprirne una nuova (con
# handshake TLS) a ogni query. Fondamentale per la latenza, specie con molte
# query per richiesta.
# ---------------------------------------------------------------------------
_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL non impostata. Configura la stringa di connessione "
                "PostgreSQL di Supabase nella variabile d'ambiente DATABASE_URL."
            )
        _pool = ConnectionPool(
            conninfo=DATABASE_URL,
            min_size=1,
            max_size=8,
            max_idle=60,
            kwargs={
                "row_factory": _row_factory,
                "autocommit": False,
                # Compatibile col pooler (pgbouncer) di Supabase in modalita
                # transaction: niente prepared statement.
                "prepare_threshold": None,
            },
            open=True,
        )
    return _pool


def get_connection() -> Connection:
    """Preleva una connessione dal pool (accesso ai campi per nome)."""
    pool = _get_pool()
    raw = pool.getconn()
    return Connection(raw, pool)


# ---------------------------------------------------------------------------
# Schema (idempotente). Rispecchia lo schema SQLite con tipi PostgreSQL
# compatibili: booleani come integer (0/1), date come text, niente vincoli di
# foreign key (come SQLite di default), cosi il resto del codice non cambia.
# ---------------------------------------------------------------------------
_TS_DEFAULT = "to_char((now() at time zone 'utc'), 'YYYY-MM-DD HH24:MI:SS')"

_SCHEMA_STATEMENTS = [
    f"""
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        created_at TEXT DEFAULT {_TS_DEFAULT}
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        full_name TEXT NOT NULL,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        is_admin INTEGER NOT NULL DEFAULT 0,
        auth_version INTEGER NOT NULL DEFAULT 1,
        account_type TEXT NOT NULL DEFAULT 'couple',
        partner_invite TEXT NOT NULL DEFAULT '',
        couple_id TEXT NOT NULL DEFAULT '',
        avatar_id TEXT NOT NULL DEFAULT '1',
        email TEXT DEFAULT '',
        created_at TEXT DEFAULT {_TS_DEFAULT}
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS user_categories (
        id TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        normalized_name TEXT NOT NULL,
        color TEXT NOT NULL,
        icon TEXT NOT NULL,
        is_default INTEGER NOT NULL DEFAULT 0,
        deletable INTEGER NOT NULL DEFAULT 1,
        is_monthly_custom INTEGER NOT NULL DEFAULT 0,
        month_label TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT {_TS_DEFAULT},
        updated_at TEXT DEFAULT {_TS_DEFAULT},
        UNIQUE(user_id, normalized_name, is_monthly_custom, month_label)
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS expenses (
        id SERIAL PRIMARY KEY,
        expense_date TEXT NOT NULL,
        amount DOUBLE PRECISION NOT NULL CHECK(amount > 0),
        name TEXT NOT NULL DEFAULT '',
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        paid_by TEXT NOT NULL,
        expense_type TEXT NOT NULL CHECK(expense_type IN ('Personale', 'Condivisa')),
        owner TEXT,
        shared_couple_id TEXT,
        split_type TEXT NOT NULL DEFAULT 'equal',
        split_ratio DOUBLE PRECISION NOT NULL DEFAULT 0.5,
        is_settled INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT {_TS_DEFAULT},
        updated_at TEXT DEFAULT {_TS_DEFAULT}
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS incomes (
        id SERIAL PRIMARY KEY,
        income_date TEXT NOT NULL,
        amount DOUBLE PRECISION NOT NULL CHECK(amount > 0),
        source TEXT NOT NULL,
        description TEXT NOT NULL,
        owner TEXT NOT NULL DEFAULT '',
        created_at TEXT DEFAULT {_TS_DEFAULT},
        updated_at TEXT DEFAULT {_TS_DEFAULT}
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS couples (
        id TEXT PRIMARY KEY,
        owner_user_id INTEGER NOT NULL,
        partner_user_id INTEGER,
        created_at TEXT DEFAULT {_TS_DEFAULT}
    )
    """,
    f"""
    CREATE TABLE IF NOT EXISTS couple_invites (
        id SERIAL PRIMARY KEY,
        invite_token TEXT NOT NULL UNIQUE,
        couple_id TEXT NOT NULL,
        owner_user_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        used_by_user_id INTEGER,
        created_at TEXT DEFAULT {_TS_DEFAULT},
        used_at TEXT
    )
    """,
]

_DEFAULT_CATEGORIES = [
    "Casa",
    "Spesa",
    "Trasporti",
    "Ristoranti",
    "Abbonamenti",
    "Svago",
    "Regali",
    "Cura persona",
    "Altro",
]


def initialize_database() -> None:
    """Crea le tabelle se mancano e inserisce le categorie di default."""
    with get_connection() as connection:
        for statement in _SCHEMA_STATEMENTS:
            connection.execute(statement)

        existing = {
            row["name"].lower()
            for row in connection.execute("SELECT name FROM categories").fetchall()
        }
        for category in _DEFAULT_CATEGORIES:
            if category.lower() not in existing:
                connection.execute(
                    "INSERT INTO categories (name) VALUES (?)", (category,)
                )
