from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "spese.db"


def get_connection() -> sqlite3.Connection:
    """Restituisce una connessione SQLite con accesso ai campi per nome."""
    DATA_DIR.mkdir(exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    """Crea le tabelle principali e inserisce dati demo al primo avvio."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_user_email_column(connection)

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                name TEXT NOT NULL DEFAULT '',
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                paid_by TEXT NOT NULL,
                expense_type TEXT NOT NULL CHECK(expense_type IN ('Personale', 'Condivisa')),
                owner TEXT,
                split_type TEXT NOT NULL DEFAULT 'equal',
                split_ratio REAL NOT NULL DEFAULT 0.5,
                is_settled INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _migrate_expenses_schema_if_needed(connection)

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS incomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                income_date TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount > 0),
                source TEXT NOT NULL,
                description TEXT NOT NULL,
                owner TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_income_owner_column(connection)

        existing_usernames = {
            row["username"]
            for row in connection.execute("SELECT username FROM users").fetchall()
        }
        users_to_insert = []
        if "io" not in existing_usernames:
            users_to_insert.append(("Mattia", "io", "", _hash_password("")))
        if "compagna" not in existing_usernames:
            users_to_insert.append(("Compagna", "compagna", "", _hash_password("demo123")))
        if users_to_insert:
            connection.executemany(
                """
                INSERT INTO users (full_name, username, email, password_hash)
                VALUES (?, ?, ?, ?)
                """,
                users_to_insert,
            )

        usernames = [
            row["username"]
            for row in connection.execute("SELECT username FROM users ORDER BY id ASC").fetchall()
        ]
        primary_username = usernames[0] if usernames else "io"
        secondary_username = usernames[1] if len(usernames) > 1 else "compagna"
        connection.execute(
            """
            UPDATE expenses
            SET paid_by = CASE
                WHEN LOWER(paid_by) = 'io' THEN ?
                WHEN LOWER(paid_by) = 'compagna' THEN ?
                ELSE paid_by
            END
            WHERE LOWER(paid_by) IN ('io', 'compagna')
            """,
            (primary_username, secondary_username),
        )
        connection.execute(
            """
            UPDATE expenses
            SET owner = CASE
                WHEN expense_type = 'Personale' AND (owner IS NULL OR TRIM(owner) = '') THEN paid_by
                ELSE owner
            END
            """
        )

        categories_count = connection.execute("SELECT COUNT(*) AS total FROM categories").fetchone()["total"]
        if categories_count == 0:
            connection.executemany(
                """
                INSERT INTO categories (name)
                VALUES (?)
                """,
                [
                    ("Spesa",),
                    ("Casa",),
                    ("Trasporti",),
                    ("Ristoranti",),
                    ("Svago",),
                    ("Salute",),
                    ("Abbonamenti",),
                    ("Viaggi",),
                    ("Regali",),
                    ("Altro",),
                ],
            )

        count = connection.execute("SELECT COUNT(*) AS total FROM expenses").fetchone()["total"]
        if count == 0:
            connection.executemany(
                """
                INSERT INTO expenses (
                    expense_date,
                    amount,
                    name,
                    category,
                    description,
                    paid_by,
                    expense_type,
                    owner,
                    split_type,
                    split_ratio,
                    is_settled
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    ("2026-03-02", 45.50, "Supermercato", "Spesa", "Supermercato settimanale", primary_username, "Condivisa", None, "equal", 0.5, 0),
                    ("2026-03-05", 18.90, "Benzina scooter", "Trasporti", "Benzina scooter", primary_username, "Personale", primary_username, "equal", 1.0, 0),
                    ("2026-03-07", 72.00, "Bollette luce", "Casa", "Bollette luce", secondary_username, "Condivisa", None, "equal", 0.5, 0),
                    ("2026-03-10", 25.00, "Cinema", "Svago", "Cinema", secondary_username, "Condivisa", None, "custom", 0.4, 0),
                    ("2026-03-12", 32.00, "Farmacia", "Salute", "Farmacia", secondary_username, "Personale", secondary_username, "equal", 1.0, 0),
                    ("2026-02-18", 120.00, "Internet mensile", "Casa", "Internet mensile", primary_username, "Condivisa", None, "equal", 0.5, 0),
                    ("2026-02-22", 54.90, "Cena fuori", "Ristoranti", "Cena fuori", primary_username, "Condivisa", None, "custom", 0.6, 0),
                    ("2026-01-28", 89.99, "Corso online", "Abbonamenti", "Corso online", primary_username, "Personale", primary_username, "equal", 1.0, 0),
                ],
            )

        incomes_count = connection.execute("SELECT COUNT(*) AS total FROM incomes").fetchone()["total"]
        if incomes_count == 0:
            connection.executemany(
                """
                INSERT INTO incomes (
                    income_date,
                    amount,
                    source,
                    description,
                    owner
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    ("2026-03-01", 2400.00, "Stipendio", "Entrata mensile principale", primary_username),
                    ("2026-03-15", 180.00, "Extra", "Lavoretto freelance", primary_username),
                    ("2026-02-01", 2400.00, "Stipendio", "Entrata mensile principale", primary_username),
                    ("2026-01-01", 2400.00, "Stipendio", "Entrata mensile principale", primary_username),
                ],
            )


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _ensure_user_email_column(connection: sqlite3.Connection) -> None:
    columns = connection.execute("PRAGMA table_info(users)").fetchall()
    existing_names = {column["name"] for column in columns}
    if "email" in existing_names:
        return
    connection.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")


def _migrate_expenses_schema_if_needed(connection: sqlite3.Connection) -> None:
    columns = connection.execute("PRAGMA table_info(expenses)").fetchall()
    existing_names = {column["name"] for column in columns}
    needs_migration = (
        "paid_by" not in existing_names
        or "owner" not in existing_names
        or "split_type" not in existing_names
        or "split_ratio" not in existing_names
        or "is_settled" not in existing_names
        or "payer" in existing_names
        or "my_share_percentage" in existing_names
    )
    if not needs_migration:
        connection.execute(
            """
            UPDATE expenses
            SET owner = CASE
                WHEN expense_type = 'Personale' AND (owner IS NULL OR TRIM(owner) = '') THEN paid_by
                ELSE owner
            END
            """
        )
        return

    source_paid_column = "paid_by" if "paid_by" in existing_names else "payer"
    source_owner_column = "owner" if "owner" in existing_names else source_paid_column
    source_name_column = "name" if "name" in existing_names else "description"
    source_split_type_expr = (
        "CASE WHEN split_type = 'Personalizzata' THEN 'custom' ELSE 'equal' END"
        if "split_type" in existing_names
        else "'equal'"
    )
    source_split_ratio_expr = "0.5"
    source_is_settled_expr = "COALESCE(is_settled, 0)" if "is_settled" in existing_names else "0"

    connection.execute("DROP TABLE IF EXISTS expenses_new")
    connection.execute(
        """
        CREATE TABLE expenses_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            name TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            paid_by TEXT NOT NULL,
            expense_type TEXT NOT NULL CHECK(expense_type IN ('Personale', 'Condivisa')),
            owner TEXT,
            split_type TEXT NOT NULL DEFAULT 'equal',
            split_ratio REAL NOT NULL DEFAULT 0.5,
            is_settled INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        f"""
        INSERT INTO expenses_new (
            id,
            expense_date,
            amount,
            name,
            category,
            description,
            paid_by,
            expense_type,
            owner,
            split_type,
            split_ratio,
            is_settled,
            created_at,
            updated_at
        )
        SELECT
            id,
            expense_date,
            amount,
            COALESCE(NULLIF(TRIM({source_name_column}), ''), TRIM(description), 'Spesa'),
            category,
            description,
            CASE
                WHEN LOWER({source_paid_column}) = 'io' THEN 'io'
                WHEN LOWER({source_paid_column}) = 'compagna' THEN 'compagna'
                ELSE {source_paid_column}
            END,
            expense_type,
            CASE
                WHEN expense_type = 'Personale' THEN
                    CASE
                        WHEN LOWER({source_owner_column}) = 'io' THEN 'io'
                        WHEN LOWER({source_owner_column}) = 'compagna' THEN 'compagna'
                        ELSE {source_owner_column}
                    END
                ELSE NULL
            END,
            CASE
                WHEN expense_type = 'Personale' THEN 'equal'
                ELSE {source_split_type_expr}
            END,
            CASE
                WHEN expense_type = 'Personale' THEN 1.0
                ELSE {source_split_ratio_expr}
            END,
            CASE
                WHEN expense_type = 'Personale' THEN 0
                ELSE {source_is_settled_expr}
            END,
            created_at,
            updated_at
        FROM expenses
        """
    )
    connection.execute("DROP TABLE expenses")
    connection.execute("ALTER TABLE expenses_new RENAME TO expenses")


def _ensure_income_owner_column(connection: sqlite3.Connection) -> None:
    columns = connection.execute("PRAGMA table_info(incomes)").fetchall()
    existing_names = {column["name"] for column in columns}
    if "owner" not in existing_names:
        connection.execute("ALTER TABLE incomes ADD COLUMN owner TEXT DEFAULT ''")

    first_user = connection.execute("SELECT username FROM users ORDER BY id ASC LIMIT 1").fetchone()
    default_owner = first_user["username"] if first_user is not None else "io"
    connection.execute(
        """
        UPDATE incomes
        SET owner = ?
        WHERE owner IS NULL OR TRIM(owner) = ''
        """,
        (default_owner,),
    )
