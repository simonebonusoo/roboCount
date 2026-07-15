from __future__ import annotations

import base64
import binascii
import calendar
import hashlib
import hmac
import os
import re
import secrets
from datetime import date, datetime
from io import BytesIO
from io import StringIO

import pandas as pd

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ModuleNotFoundError:
    REPORTLAB_AVAILABLE = False

from database import get_connection


EXPENSE_TYPE_OPTIONS = ["Personale", "Condivisa"]
SHARED_SPLIT_OPTIONS = ["equal", "custom"]
DEFAULT_CATEGORY_DEFINITIONS = [
    {"id": "casa", "name": "Casa", "color": "#22c55e", "icon": "home", "isDefault": True, "deletable": False},
    {"id": "spesa", "name": "Spesa", "color": "#f59e0b", "icon": "shopping-cart", "isDefault": True, "deletable": False},
    {"id": "trasporti", "name": "Trasporti", "color": "#a855f7", "icon": "car", "isDefault": True, "deletable": False},
    {"id": "ristoranti", "name": "Ristoranti", "color": "#f59e0b", "icon": "utensils", "isDefault": True, "deletable": False},
    {"id": "abbonamenti", "name": "Abbonamenti", "color": "#3b82f6", "icon": "receipt", "isDefault": True, "deletable": False},
    {"id": "svago", "name": "Svago", "color": "#3b82f6", "icon": "gamepad", "isDefault": True, "deletable": False},
    {"id": "regali", "name": "Regali", "color": "#a855f7", "icon": "gift", "isDefault": True, "deletable": False},
    {"id": "cura-persona", "name": "Cura persona", "color": "#63d72a", "icon": "heart", "isDefault": True, "deletable": False},
    {"id": "altro", "name": "Altro", "color": "#6b7280", "icon": "more-horizontal", "isDefault": True, "deletable": False},
]
CATEGORY_OPTIONS = [category["name"] for category in DEFAULT_CATEGORY_DEFINITIONS]
_CATEGORY_METADATA = {category["name"].lower(): category for category in DEFAULT_CATEGORY_DEFINITIONS}
_CATEGORY_PALETTE = ["#22c55e", "#f59e0b", "#a855f7", "#3b82f6", "#6b7280", "#63d72a"]
CALENDAR_MONTH_NAMES = {
    "01": "Gennaio",
    "02": "Febbraio",
    "03": "Marzo",
    "04": "Aprile",
    "05": "Maggio",
    "06": "Giugno",
    "07": "Luglio",
    "08": "Agosto",
    "09": "Settembre",
    "10": "Ottobre",
    "11": "Novembre",
    "12": "Dicembre",
}

PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 310000
LEGACY_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_HASH_ITERATIONS,
    )
    encoded_salt = base64.b64encode(salt).decode("ascii")
    encoded_hash = base64.b64encode(derived_key).decode("ascii")
    return f"{PASSWORD_HASH_SCHEME}${PASSWORD_HASH_ITERATIONS}${encoded_salt}${encoded_hash}"


def _verify_password_hash(password: str, stored_hash: str) -> bool:
    try:
        scheme, iteration_text, encoded_salt, encoded_hash = stored_hash.split("$", 3)
    except ValueError:
        return False
    if scheme != PASSWORD_HASH_SCHEME:
        return False
    try:
        iterations = int(iteration_text)
        salt = base64.b64decode(encoded_salt.encode("ascii"))
        expected_hash = base64.b64decode(encoded_hash.encode("ascii"))
    except (ValueError, binascii.Error):
        return False

    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(derived_key, expected_hash)


def _is_legacy_password_hash(stored_hash: str) -> bool:
    return bool(LEGACY_SHA256_PATTERN.fullmatch((stored_hash or "").strip().lower()))


def _build_user_payload(row: dict) -> dict:
    couple_id = row.get("couple_id") or row.get("username") or ""
    return {
        "id": row["id"],
        "full_name": row.get("full_name", ""),
        "username": row.get("username", ""),
        "email": row.get("email", "") or "",
        "is_admin": bool(row.get("is_admin", False)),
        "auth_version": int(row.get("auth_version", 1) or 1),
        "account_type": row.get("account_type", "couple") or "couple",
        "partner_invite": row.get("partner_invite", "") or "",
        "couple_id": "" if row.get("account_type") == "personal" else couple_id,
        "avatar_id": str(row.get("avatar_id", "1") or "1"),
    }


def get_user_by_username(username: str) -> dict | None:
    clean_username = username.strip().lower()
    if not clean_username:
        return None
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, full_name, username, email, password_hash, is_admin, auth_version, account_type, partner_invite, couple_id, avatar_id
            FROM users
            WHERE LOWER(username) = LOWER(?)
            """,
            (clean_username,),
        ).fetchone()
    return _build_user_payload(dict(row)) if row is not None else None


def authenticate_user(username: str, password: str) -> dict | None:
    """Verifica le credenziali dell'utente e restituisce i dati base se valide."""
    clean_username = username.strip().lower()
    if not clean_username:
        return None

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, full_name, username, email, password_hash, is_admin, auth_version, account_type, partner_invite, couple_id, avatar_id
            FROM users
            WHERE LOWER(username) = LOWER(?)
            """,
            (clean_username,),
        ).fetchone()
        if row is None:
            return None

        stored_hash = row["password_hash"] or ""
        legacy_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        password_matches = False
        should_upgrade_hash = False
        if _is_legacy_password_hash(stored_hash):
            password_matches = hmac.compare_digest(stored_hash, legacy_hash)
            should_upgrade_hash = password_matches
        else:
            password_matches = _verify_password_hash(password, stored_hash)

        if not password_matches:
            return None

        if should_upgrade_hash:
            upgraded_hash = hash_password(password)
            connection.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (upgraded_hash, row["id"]),
            )
            row = connection.execute(
                """
                SELECT id, full_name, username, email, password_hash, is_admin, auth_version, account_type, partner_invite, couple_id, avatar_id
                FROM users
                WHERE id = ?
                """,
                (row["id"],),
            ).fetchone()

    return _build_user_payload(dict(row)) if row is not None else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, full_name, username, email, is_admin, auth_version, account_type, partner_invite, couple_id, avatar_id
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    return _build_user_payload(dict(row)) if row is not None else None


def _normalize_avatar_id(avatar_id: str) -> str:
    clean_avatar_id = str(avatar_id or "1").strip()
    return clean_avatar_id if clean_avatar_id in {"1", "2", "3", "4", "5", "6", "7", "8"} else "1"


def _get_open_invite(connection, invite_token: str):
    clean_token = invite_token.strip()
    if not clean_token:
        return None
    return connection.execute(
        """
        SELECT couple_invites.id, couple_invites.invite_token, couple_invites.couple_id, couple_invites.owner_user_id, couples.partner_user_id
        FROM couple_invites
        JOIN couples ON couples.id = couple_invites.couple_id
        WHERE couple_invites.invite_token = ? AND couple_invites.status = 'open'
        """,
        (clean_token,),
    ).fetchone()


def _ensure_couple_row(connection, couple_id: str, owner_user_id: int) -> None:
    connection.execute(
        """
        INSERT INTO couples (id, owner_user_id, partner_user_id)
        VALUES (?, ?, NULL)
        ON CONFLICT(id) DO NOTHING
        """,
        (couple_id, owner_user_id),
    )


def _couple_member_count(connection, couple_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) AS total FROM users WHERE account_type = 'couple' AND couple_id = ?",
        (couple_id,),
    ).fetchone()
    return int(row["total"] or 0) if row is not None else 0


def create_user(
    full_name: str,
    username: str,
    email: str,
    password: str,
    account_type: str = "couple",
    partner_invite: str = "",
    avatar_id: str = "1",
) -> tuple[bool, str, dict | None]:
    clean_name = full_name.strip()
    clean_username = username.strip().lower()
    clean_email = email.strip()
    clean_account_type = account_type.strip().lower() if account_type else "couple"
    clean_partner_invite = partner_invite.strip()
    clean_avatar_id = _normalize_avatar_id(avatar_id)

    if not clean_name:
        return False, "Il nome non puo essere vuoto.", None
    if not clean_username:
        return False, "Lo username non puo essere vuoto.", None
    if not password:
        return False, "La password non puo essere vuota.", None
    if clean_account_type not in {"personal", "couple"}:
        return False, "Tipo account non valido.", None
    if clean_account_type == "personal":
        clean_partner_invite = ""

    with get_connection() as connection:
        try:
            connection.execute("BEGIN")
            existing = connection.execute(
                "SELECT id FROM users WHERE LOWER(username) = LOWER(?)",
                (clean_username,),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                return False, "Questo username e gia in uso.", None

            users_count = connection.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
            is_admin = 1 if int(users_count or 0) == 0 else 0
            if is_admin:
                clean_account_type = "personal"
                clean_partner_invite = ""
            couple_id = ""
            invite_row = None

            if clean_account_type == "couple":
                if clean_partner_invite:
                    invite_row = _get_open_invite(connection, clean_partner_invite)
                    if invite_row is None:
                        connection.rollback()
                        return False, "Invito partner non valido o gia usato.", None
                    couple_id = invite_row["couple_id"]
                    if _couple_member_count(connection, couple_id) >= 2 or invite_row["partner_user_id"] is not None:
                        connection.rollback()
                        return False, "Questa coppia e gia completa.", None
                else:
                    couple_id = clean_username

            cursor = connection.execute(
                """
                INSERT INTO users (full_name, username, email, password_hash, is_admin, auth_version, account_type, partner_invite, couple_id, avatar_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_name,
                    clean_username,
                    clean_email,
                    hash_password(password),
                    is_admin,
                    1,
                    clean_account_type,
                    clean_partner_invite,
                    couple_id,
                    clean_avatar_id,
                ),
            )
            user_id = int(cursor.lastrowid)
            _ensure_user_categories_for_connection(connection, user_id)

            if clean_account_type == "couple" and invite_row is None:
                _ensure_couple_row(connection, couple_id, user_id)
            elif clean_account_type == "couple" and invite_row is not None:
                connection.execute(
                    "UPDATE couples SET partner_user_id = ? WHERE id = ?",
                    (user_id, couple_id),
                )
                connection.execute(
                    """
                    UPDATE couple_invites
                    SET status = 'used', used_by_user_id = ?, used_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (user_id, invite_row["id"]),
                )
                connection.execute(
                    "UPDATE couple_invites SET status = 'completed' WHERE couple_id = ? AND status = 'open'",
                    (couple_id,),
                )

            connection.commit()
        except Exception:
            connection.rollback()
            raise

    created_user = get_user_by_id(user_id)
    return True, "Registrazione completata.", created_user

def list_users() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, full_name, username, email, is_admin, account_type, partner_invite, couple_id, avatar_id, created_at
            FROM users
            ORDER BY id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]



def create_couple_invite(current_username: str) -> tuple[bool, str, dict | None]:
    clean_username = current_username.strip().lower()
    if not clean_username:
        return False, "Utente non valido.", None

    with get_connection() as connection:
        try:
            connection.execute("BEGIN")
            user = connection.execute(
                """
                SELECT id, username, is_admin, account_type, couple_id
                FROM users
                WHERE LOWER(username) = LOWER(?)
                """,
                (clean_username,),
            ).fetchone()
            if user is None:
                connection.rollback()
                return False, "Utente non trovato.", None
            if user["account_type"] != "couple":
                connection.rollback()
                return False, "Gli inviti partner sono disponibili solo per account coppia.", None
            if bool(user["is_admin"] if "is_admin" in user.keys() else False):
                connection.rollback()
                return False, "L'account admin non puo avere un partner.", None

            couple_id = user["couple_id"] or user["username"]
            _ensure_couple_row(connection, couple_id, int(user["id"]))
            couple = connection.execute(
                "SELECT owner_user_id, partner_user_id FROM couples WHERE id = ?",
                (couple_id,),
            ).fetchone()
            if couple is None or int(couple["owner_user_id"]) != int(user["id"]):
                connection.rollback()
                return False, "Solo il proprietario iniziale puo generare l'invito partner.", None
            if _couple_member_count(connection, couple_id) >= 2 or couple["partner_user_id"] is not None:
                connection.rollback()
                return False, "Questa coppia e gia completa.", None

            token = secrets.token_urlsafe(24)
            connection.execute(
                """
                INSERT INTO couple_invites (invite_token, couple_id, owner_user_id, status)
                VALUES (?, ?, ?, 'open')
                """,
                (token, couple_id, int(user["id"])),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return True, "Invito partner generato.", {"invite_token": token, "couple_id": couple_id}


def update_user_avatar(user_id: int, avatar_id: str) -> tuple[bool, str, dict | None]:
    clean_avatar_id = _normalize_avatar_id(avatar_id)
    with get_connection() as connection:
        row = connection.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            return False, "Utente non trovato.", None
        connection.execute("UPDATE users SET avatar_id = ? WHERE id = ?", (clean_avatar_id, user_id))
    updated_user = get_user_by_id(user_id)
    return True, "Avatar aggiornato.", updated_user

def is_admin_user(username: str) -> bool:
    clean_username = username.strip().lower()
    if not clean_username:
        return False
    with get_connection() as connection:
        row = connection.execute(
            "SELECT is_admin FROM users WHERE LOWER(username) = LOWER(?)",
            (clean_username,),
        ).fetchone()
    return bool(row["is_admin"]) if row is not None else False


def get_usernames() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT username FROM users ORDER BY id ASC"
        ).fetchall()
    return [row["username"] for row in rows]


def get_couple_member_usernames(current_username: str) -> list[str]:
    clean_username = current_username.strip().lower()
    if not clean_username:
        return []
    with get_connection() as connection:
        current_user = connection.execute(
            """
            SELECT username, account_type, couple_id
            FROM users
            WHERE LOWER(username) = LOWER(?)
            """,
            (clean_username,),
        ).fetchone()
        if current_user is None:
            return []
        if current_user["account_type"] != "couple":
            return [current_user["username"]]
        couple_id = current_user["couple_id"] or current_user["username"]
        rows = connection.execute(
            """
            SELECT username
            FROM users
            WHERE account_type = 'couple' AND couple_id = ?
            ORDER BY id ASC
            """,
            (couple_id,),
        ).fetchall()
    return [row["username"] for row in rows]


def get_couple_member_details(current_username: str) -> list[dict]:
    clean_username = current_username.strip().lower()
    if not clean_username:
        return []
    with get_connection() as connection:
        current_user = connection.execute(
            """
            SELECT username, account_type, couple_id
            FROM users
            WHERE LOWER(username) = LOWER(?)
            """,
            (clean_username,),
        ).fetchone()
        if current_user is None:
            return []
        if current_user["account_type"] != "couple":
            couple_filter = "LOWER(username) = LOWER(?)"
            params = (current_user["username"],)
        else:
            couple_id = current_user["couple_id"] or current_user["username"]
            couple_filter = "account_type = 'couple' AND couple_id = ?"
            params = (couple_id,)
        rows = connection.execute(
            f"""
            SELECT id, full_name, username, email, is_admin, auth_version, account_type, partner_invite, couple_id, avatar_id
            FROM users
            WHERE {couple_filter}
            ORDER BY id ASC
            """,
            params,
        ).fetchall()
    return [_build_user_payload(dict(row)) for row in rows]


def get_user_couple_id(username: str) -> str:
    user = get_user_by_username(username)
    if user is None:
        return ""
    return user.get("couple_id", "") if user.get("account_type") == "couple" else ""


def get_admin_count(connection=None) -> int:
    if connection is not None:
        row = connection.execute("SELECT COUNT(*) AS total FROM users WHERE is_admin = 1").fetchone()
        return int(row["total"]) if row is not None else 0
    with get_connection() as own_connection:
        row = own_connection.execute("SELECT COUNT(*) AS total FROM users WHERE is_admin = 1").fetchone()
    return int(row["total"]) if row is not None else 0


def get_couple_usernames() -> tuple[str, str]:
    usernames = get_usernames()
    if len(usernames) >= 2:
        first = usernames[0]
        second = usernames[1]
        return first, second
    first = usernames[0] if usernames else ""
    second = usernames[0] if usernames else ""
    return first, second


def get_partner_username(current_username: str) -> str:
    members = get_couple_member_usernames(current_username)
    for member in members:
        if member != current_username:
            return member
    return current_username


def _resolve_couple_id(
    connection,
    username: str,
    account_type: str,
    partner_invite: str,
    *,
    exclude_user_id: int | None = None,
) -> str:
    del exclude_user_id
    if account_type != "couple":
        return ""
    clean_username = username.strip().lower()
    clean_partner_invite = partner_invite.strip()
    if not clean_partner_invite:
        return clean_username
    invite = _get_open_invite(connection, clean_partner_invite)
    if invite is None:
        return clean_username
    return invite["couple_id"]

def _sync_partner_invites(connection, old_username: str, new_username: str) -> None:
    if old_username == new_username:
        return
    connection.execute(
        "UPDATE users SET partner_invite = ? WHERE LOWER(partner_invite) = LOWER(?)",
        (new_username, old_username),
    )


def _sync_shared_expense_couple_ids(connection) -> None:
    connection.execute(
        """
        UPDATE expenses
        SET shared_couple_id = CASE
            WHEN expense_type = 'Condivisa' THEN (
                SELECT CASE
                    WHEN users.account_type = 'couple' THEN users.couple_id
                    ELSE ''
                END
                FROM users
                WHERE LOWER(users.username) = LOWER(expenses.paid_by)
            )
            ELSE NULL
        END
        """
    )


def _propagate_couple_id_rename(connection, old_couple_id: str, new_couple_id: str) -> None:
    if not old_couple_id or not new_couple_id or old_couple_id == new_couple_id:
        return
    connection.execute(
        "UPDATE users SET couple_id = ? WHERE account_type = 'couple' AND couple_id = ?",
        (new_couple_id, old_couple_id),
    )


def update_user_profile(
    user_id: int,
    full_name: str,
    username: str,
    email: str,
    new_password: str = "",
) -> tuple[bool, str, dict | None]:
    clean_name = full_name.strip()
    clean_username = username.strip().lower()
    clean_email = email.strip()

    if not clean_name:
        return False, "Il nome non puo essere vuoto.", None
    if not clean_username:
        return False, "Lo username non puo essere vuoto.", None

    with get_connection() as connection:
        try:
            connection.execute("BEGIN")
            current_user = connection.execute(
                "SELECT username, account_type, couple_id, partner_invite FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if current_user is None:
                connection.rollback()
                return False, "Utente non trovato.", None

            old_username = current_user["username"]
            old_account_type = current_user["account_type"] or "couple"
            old_couple_id = current_user["couple_id"] or old_username
            existing = connection.execute(
                "SELECT id FROM users WHERE LOWER(username) = LOWER(?) AND id != ?",
                (clean_username, user_id),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                return False, "Questo username e gia in uso.", None

            new_couple_id = old_couple_id if old_account_type == "couple" else ""

            if new_password.strip():
                connection.execute(
                    """
                    UPDATE users
                    SET full_name = ?, username = ?, email = ?, couple_id = ?, password_hash = ?, auth_version = auth_version + 1
                    WHERE id = ?
                    """,
                    (clean_name, clean_username, clean_email, new_couple_id, hash_password(new_password), user_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET full_name = ?, username = ?, email = ?, couple_id = ?
                    WHERE id = ?
                    """,
                    (clean_name, clean_username, clean_email, new_couple_id, user_id),
                )

            if old_username != clean_username:
                _sync_partner_invites(connection, old_username, clean_username)
                connection.execute(
                    "UPDATE expenses SET paid_by = ? WHERE paid_by = ?",
                    (clean_username, old_username),
                )
                connection.execute(
                    "UPDATE expenses SET owner = ? WHERE owner = ?",
                    (clean_username, old_username),
                )
                connection.execute(
                    "UPDATE incomes SET owner = ? WHERE owner = ?",
                    (clean_username, old_username),
                )
                if old_account_type == "couple" and old_couple_id == old_username and new_couple_id == clean_username:
                    _propagate_couple_id_rename(connection, old_couple_id, new_couple_id)

            _sync_shared_expense_couple_ids(connection)

            connection.commit()
        except Exception:
            connection.rollback()
            raise

    updated_user = get_user_by_id(user_id)
    return True, "Profilo aggiornato con successo.", updated_user


def admin_update_user(
    user_id: int,
    full_name: str,
    username: str,
    email: str,
    account_type: str,
    partner_invite: str,
    is_admin: bool,
    new_password: str = "",
) -> tuple[bool, str, dict | None, bool]:
    clean_name = full_name.strip()
    clean_username = username.strip().lower()
    clean_email = email.strip()
    clean_account_type = account_type.strip().lower() if account_type else "couple"
    clean_partner_invite = partner_invite.strip()

    if not clean_name:
        return False, "Il nome non puo essere vuoto.", None, False
    if not clean_username:
        return False, "Lo username non puo essere vuoto.", None, False
    if clean_account_type not in {"personal", "couple"}:
        return False, "Tipo account non valido.", None, False
    if is_admin:
        clean_account_type = "personal"
        clean_partner_invite = ""
    if clean_account_type == "personal":
        clean_partner_invite = ""

    with get_connection() as connection:
        try:
            connection.execute("BEGIN")
            current_user = connection.execute(
                "SELECT username, is_admin, account_type, couple_id FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if current_user is None:
                connection.rollback()
                return False, "Utente non trovato.", None, False

            existing = connection.execute(
                "SELECT id FROM users WHERE LOWER(username) = LOWER(?) AND id != ?",
                (clean_username, user_id),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                return False, "Questo username e gia in uso.", None, False

            if not is_admin and bool(current_user["is_admin"]) and get_admin_count(connection) <= 1:
                connection.rollback()
                return False, "Deve rimanere almeno un admin attivo.", None, False

            old_username = current_user["username"]
            old_account_type = current_user["account_type"] or "couple"
            old_couple_id = current_user["couple_id"] or old_username
            if clean_account_type != "couple":
                new_couple_id = ""
            elif old_account_type == "couple":
                new_couple_id = old_couple_id
            else:
                new_couple_id = clean_username
            password_changed = bool(new_password.strip())

            if password_changed:
                connection.execute(
                    """
                    UPDATE users
                    SET full_name = ?, username = ?, email = ?, is_admin = ?, account_type = ?, partner_invite = ?, couple_id = ?, password_hash = ?, auth_version = auth_version + 1
                    WHERE id = ?
                    """,
                    (
                        clean_name,
                        clean_username,
                        clean_email,
                        1 if is_admin else 0,
                        clean_account_type,
                        clean_partner_invite,
                        new_couple_id,
                        hash_password(new_password),
                        user_id,
                    ),
                )
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET full_name = ?, username = ?, email = ?, is_admin = ?, account_type = ?, partner_invite = ?, couple_id = ?
                    WHERE id = ?
                    """,
                    (
                        clean_name,
                        clean_username,
                        clean_email,
                        1 if is_admin else 0,
                        clean_account_type,
                        clean_partner_invite,
                        new_couple_id,
                        user_id,
                    ),
                )

            if old_username != clean_username:
                _sync_partner_invites(connection, old_username, clean_username)
                connection.execute("UPDATE expenses SET paid_by = ? WHERE paid_by = ?", (clean_username, old_username))
                connection.execute("UPDATE expenses SET owner = ? WHERE owner = ?", (clean_username, old_username))
                connection.execute("UPDATE incomes SET owner = ? WHERE owner = ?", (clean_username, old_username))

            if old_account_type == "couple" and old_couple_id == old_username and new_couple_id == clean_username:
                _propagate_couple_id_rename(connection, old_couple_id, new_couple_id)

            _sync_shared_expense_couple_ids(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    updated_user = get_user_by_id(user_id)
    return True, "Utente aggiornato con successo.", updated_user, password_changed


def admin_delete_user(user_id: int) -> tuple[bool, str]:
    with get_connection() as connection:
        try:
            connection.execute("BEGIN")
            current_user = connection.execute(
                "SELECT username, is_admin FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if current_user is None:
                connection.rollback()
                return False, "Utente non trovato."

            if bool(current_user["is_admin"]) and get_admin_count(connection) <= 1:
                connection.rollback()
                return False, "Non puoi eliminare l'ultimo admin."

            username = current_user["username"]
            connection.execute("DELETE FROM expenses WHERE paid_by = ? OR owner = ?", (username, username))
            connection.execute("DELETE FROM incomes WHERE owner = ?", (username,))
            connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
            connection.execute("UPDATE users SET partner_invite = '' WHERE LOWER(partner_invite) = LOWER(?)", (username,))
            _sync_shared_expense_couple_ids(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return True, "Utente eliminato con successo."


def _normalize_category_name(name: str) -> str:
    return " ".join(str(name or "").strip().split()).lower()


def _month_label_from_value(value: str | date | datetime | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m")
    if isinstance(value, date):
        return value.strftime("%Y-%m")
    text = str(value).strip()
    if not text or text == "Tutti":
        return ""
    if re.fullmatch(r"\d{4}-\d{2}", text):
        return text
    try:
        return datetime.fromisoformat(text).strftime("%Y-%m")
    except ValueError:
        return ""


def _default_category_metadata(name: str) -> dict:
    metadata = _CATEGORY_METADATA.get(_normalize_category_name(name))
    if metadata:
        return metadata
    index = abs(hash(_normalize_category_name(name))) % len(_CATEGORY_PALETTE)
    return {
        "id": f"custom-{_normalize_category_name(name).replace(' ', '-')}",
        "name": name,
        "color": _CATEGORY_PALETTE[index],
        "icon": "tag",
        "isDefault": False,
        "deletable": True,
    }


def _serialize_category(row: dict, used_count: int = 0) -> dict:
    is_monthly = bool(row.get("is_monthly_custom", row.get("isMonthlyCustom", False)))
    is_system_default = bool(row.get("is_default", row.get("isDefault", False)))
    base_deletable = bool(row.get("deletable", True))
    return {
        "id": str(row.get("id") or _default_category_metadata(row.get("name", ""))["id"]),
        "name": row.get("name", ""),
        "color": row.get("color") or _default_category_metadata(row.get("name", ""))["color"],
        "icon": row.get("icon") or _default_category_metadata(row.get("name", ""))["icon"],
        "isDefault": is_system_default,
        "isSystemDefault": is_system_default,
        "deletable": base_deletable and not is_system_default and (not is_monthly or used_count == 0),
        "isMonthlyCustom": is_monthly,
        "scope": "monthly_custom" if is_monthly else "user_default",
        "monthLabel": row.get("month_label", row.get("monthLabel", "")) or "",
        "usedCount": int(used_count or 0),
        "expenseCount": int(used_count or 0),
        "lockedReason": "Questa categoria contiene spese e non puo essere eliminata." if is_monthly and used_count > 0 else "",
    }


def _ensure_user_categories_for_connection(connection, user_id: int) -> None:
    for category in DEFAULT_CATEGORY_DEFINITIONS:
        connection.execute(
            """
            INSERT OR IGNORE INTO user_categories (
                id, user_id, name, normalized_name, color, icon, is_default, deletable, is_monthly_custom, month_label
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, 0, 0, '')
            """,
            (
                f"user-{user_id}-{category['id']}",
                user_id,
                category["name"],
                _normalize_category_name(category["name"]),
                category["color"],
                category["icon"],
            ),
        )


def ensure_user_categories(username: str) -> None:
    clean_username = username.strip().lower()
    if not clean_username:
        return
    with get_connection() as connection:
        user = connection.execute(
            "SELECT id FROM users WHERE LOWER(username) = LOWER(?)",
            (clean_username,),
        ).fetchone()
        if user is None:
            return
        _ensure_user_categories_for_connection(connection, int(user["id"]))


def _get_user_id_for_categories(connection, username: str) -> int | None:
    user = connection.execute(
        "SELECT id FROM users WHERE LOWER(username) = LOWER(?)",
        (username.strip().lower(),),
    ).fetchone()
    return int(user["id"]) if user is not None else None


def _get_visible_expense_categories(username: str, month_label: str = "", visible_expenses: pd.DataFrame | None = None) -> list[str]:
    dataframe = visible_expenses.copy() if visible_expenses is not None else get_visible_expenses(get_expenses(), username)
    clean_month = _month_label_from_value(month_label)
    if clean_month and not dataframe.empty:
        dataframe = dataframe[dataframe["month_label"] == clean_month]
    if dataframe.empty:
        return []
    return dataframe["category"].dropna().astype(str).tolist()


def _get_visible_category_usage(username: str, month_label: str = "") -> dict[str, int]:
    usage: dict[str, int] = {}
    for category in _get_visible_expense_categories(username, month_label):
        normalized = _normalize_category_name(category)
        if normalized:
            usage[normalized] = usage.get(normalized, 0) + 1
    return usage


def get_category_items(username: str, month_label: str = "", visible_expenses: pd.DataFrame | None = None) -> list[dict]:
    clean_month = _month_label_from_value(month_label)
    ensure_user_categories(username)
    visible_categories = _get_visible_expense_categories(username, clean_month, visible_expenses)
    usage: dict[str, int] = {}
    for category in visible_categories:
        normalized = _normalize_category_name(category)
        if normalized:
            usage[normalized] = usage.get(normalized, 0) + 1
    items_by_key: dict[str, dict] = {}

    with get_connection() as connection:
        user_id = _get_user_id_for_categories(connection, username)
        if user_id is None:
            return []
        rows = connection.execute(
            """
            SELECT *
            FROM user_categories
            WHERE user_id = ?
              AND (
                is_monthly_custom = 0
                OR (is_monthly_custom = 1 AND month_label = ?)
              )
            ORDER BY is_default DESC, LOWER(name) ASC
            """,
            (user_id, clean_month),
        ).fetchall()

    for row in rows:
        row_dict = dict(row)
        normalized = _normalize_category_name(row_dict["name"])
        items_by_key[normalized] = _serialize_category(row_dict, usage.get(normalized, 0))

    for normalized, count in usage.items():
        if normalized in items_by_key:
            continue
        display_name = next(
            (category for category in visible_categories if _normalize_category_name(category) == normalized),
            normalized.title(),
        )
        metadata = _default_category_metadata(display_name)
        items_by_key[normalized] = _serialize_category(
            {
                "id": metadata["id"],
                "name": display_name,
                "color": metadata["color"],
                "icon": metadata["icon"],
                "is_default": metadata["isDefault"],
                "deletable": False,
                "is_monthly_custom": False,
                "month_label": "",
            },
            count,
        )

    return sorted(items_by_key.values(), key=lambda item: (not item["isDefault"], item["name"].lower()))


def get_categories(username: str | None = None, month_label: str = "") -> list[str]:
    if username:
        return [item["name"] for item in get_category_items(username, month_label)]
    with get_connection() as connection:
        rows = connection.execute("SELECT name FROM categories ORDER BY LOWER(name) ASC").fetchall()
    categories = [row["name"] for row in rows]
    normalized = {category.lower() for category in categories}
    restored_defaults = [category for category in CATEGORY_OPTIONS if category.lower() not in normalized]
    return sorted([*categories, *restored_defaults], key=str.lower)


def _insert_user_category(
    username: str,
    name: str,
    *,
    month_label: str = "",
    is_monthly_custom: bool = False,
    color: str = "",
    icon: str = "",
) -> tuple[bool, str, dict | None]:
    clean_name = " ".join(name.strip().split())
    if not clean_name:
        return False, "Il nome della categoria non puo essere vuoto.", None
    normalized = _normalize_category_name(clean_name)
    clean_month = _month_label_from_value(month_label)
    if is_monthly_custom and not clean_month:
        return False, "Mese categoria non valido.", None

    metadata = _default_category_metadata(clean_name)
    clean_color = color.strip() if color else metadata["color"]
    clean_icon = icon.strip() if icon else metadata["icon"]

    with get_connection() as connection:
        user_id = _get_user_id_for_categories(connection, username)
        if user_id is None:
            return False, "Utente non trovato.", None
        _ensure_user_categories_for_connection(connection, user_id)
        existing = connection.execute(
            """
            SELECT *
            FROM user_categories
            WHERE user_id = ? AND normalized_name = ? AND is_monthly_custom = ? AND month_label = ?
            """,
            (user_id, normalized, 1 if is_monthly_custom else 0, clean_month if is_monthly_custom else ""),
        ).fetchone()
        if existing is not None:
            return False, "Questa categoria esiste gia.", _serialize_category(dict(existing))

        category_id = f"cat-{user_id}-{secrets.token_hex(8)}"
        connection.execute(
            """
            INSERT INTO user_categories (
                id, user_id, name, normalized_name, color, icon, is_default, deletable, is_monthly_custom, month_label
            )
            VALUES (?, ?, ?, ?, ?, ?, 0, 1, ?, ?)
            """,
            (category_id, user_id, clean_name, normalized, clean_color, clean_icon, 1 if is_monthly_custom else 0, clean_month if is_monthly_custom else ""),
        )
        row = connection.execute("SELECT * FROM user_categories WHERE id = ?", (category_id,)).fetchone()
    return True, "Categoria aggiunta con successo.", _serialize_category(dict(row)) if row else None


def add_category(name: str, username: str | None = None, month_label: str = "", color: str = "", icon: str = "") -> tuple[bool, str, dict | None]:
    if username:
        return _insert_user_category(username, name, month_label=month_label, is_monthly_custom=True, color=color, icon=icon)

    clean_name = name.strip()
    if not clean_name:
        return False, "Il nome della categoria non puo essere vuoto.", None
    with get_connection() as connection:
        existing = connection.execute("SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (clean_name,)).fetchone()
        if existing is not None:
            return False, "Questa categoria esiste gia.", None
        connection.execute("INSERT INTO categories (name) VALUES (?)", (clean_name,))
    return True, "Categoria aggiunta con successo.", None


def add_personal_category(username: str, name: str, color: str = "", icon: str = "") -> tuple[bool, str, dict | None]:
    return _insert_user_category(username, name, is_monthly_custom=False, color=color, icon=icon)


def _expense_usage_count_for_category(username: str, category_name: str, month_label: str = "") -> int:
    usage = _get_visible_category_usage(username, _month_label_from_value(month_label))
    return int(usage.get(_normalize_category_name(category_name), 0))


def delete_category(name: str, username: str | None = None, month_label: str = "") -> tuple[bool, str]:
    clean_name = name.strip()
    if not clean_name:
        return False, "Categoria non valida."
    if username:
        clean_month = _month_label_from_value(month_label)
        with get_connection() as connection:
            user_id = _get_user_id_for_categories(connection, username)
            if user_id is None:
                return False, "Utente non trovato."
            row = connection.execute(
                """
                SELECT *
                FROM user_categories
                WHERE user_id = ? AND normalized_name = ? AND is_monthly_custom = 1 AND month_label = ?
                """,
                (user_id, _normalize_category_name(clean_name), clean_month),
            ).fetchone()
            if row is None:
                if _expense_usage_count_for_category(username, clean_name, clean_month) > 0:
                    return False, "Questa categoria contiene spese e non puo essere eliminata."
                deleted = connection.execute(
                    """
                    DELETE FROM user_categories
                    WHERE user_id = ? AND normalized_name = ? AND is_default = 0 AND deletable = 1
                      AND (is_monthly_custom = 1 OR is_monthly_custom = 0)
                    """,
                    (user_id, _normalize_category_name(clean_name)),
                ).rowcount
                legacy_deleted = connection.execute(
                    "DELETE FROM categories WHERE LOWER(name) = LOWER(?)",
                    (clean_name,),
                ).rowcount
                if deleted or legacy_deleted:
                    return True, "Categoria eliminata con successo."
                return False, "Questa categoria non esiste nel mese corrente."
            if bool(row["is_default"]) or not bool(row["deletable"]):
                return False, "Non puoi eliminare una categoria di partenza."
            if _expense_usage_count_for_category(username, clean_name, clean_month) > 0:
                return False, "Questa categoria contiene spese e non puo essere eliminata."
            connection.execute("DELETE FROM user_categories WHERE id = ?", (row["id"],))
        return True, "Categoria eliminata con successo."

    if clean_name.lower() in {category.lower() for category in CATEGORY_OPTIONS}:
        return False, "Non puoi eliminare una categoria di partenza."
    with get_connection() as connection:
        existing = connection.execute("SELECT id FROM categories WHERE LOWER(name) = LOWER(?)", (clean_name,)).fetchone()
        if existing is None:
            return False, "Questa categoria non esiste."
        connection.execute("DELETE FROM categories WHERE LOWER(name) = LOWER(?)", (clean_name,))
    return True, "Categoria eliminata con successo."


def get_personal_categories(username: str) -> list[dict]:
    ensure_user_categories(username)
    usage = _get_visible_category_usage(username, "")
    with get_connection() as connection:
        user_id = _get_user_id_for_categories(connection, username)
        if user_id is None:
            return []
        rows = connection.execute(
            """
            SELECT *
            FROM user_categories
            WHERE user_id = ? AND is_monthly_custom = 0
            ORDER BY is_default DESC, LOWER(name) ASC
            """,
            (user_id,),
        ).fetchall()
    return [_serialize_category(dict(row), usage.get(_normalize_category_name(row["name"]), 0)) for row in rows]


def get_monthly_categories(username: str, month_label: str) -> list[dict]:
    clean_month = _month_label_from_value(month_label) or datetime.today().strftime("%Y-%m")
    ensure_user_categories(username)
    usage = _get_visible_category_usage(username, clean_month)
    with get_connection() as connection:
        user_id = _get_user_id_for_categories(connection, username)
        if user_id is None:
            return []
        rows = connection.execute(
            """
            SELECT *
            FROM user_categories
            WHERE user_id = ? AND is_monthly_custom = 1 AND month_label = ?
            ORDER BY LOWER(name) ASC
            """,
            (user_id, clean_month),
        ).fetchall()
    return [_serialize_category(dict(row), usage.get(_normalize_category_name(row["name"]), 0)) for row in rows]


def _rename_visible_expense_category(connection, username: str, old_name: str, new_name: str, month_label: str = "") -> None:
    clean_month = _month_label_from_value(month_label)
    user = connection.execute(
        "SELECT username, account_type, couple_id FROM users WHERE LOWER(username) = LOWER(?)",
        (username.strip().lower(),),
    ).fetchone()
    if user is None:
        return
    params = [new_name, old_name, user["username"]]
    month_clause = ""
    if clean_month:
        month_clause = " AND substr(expense_date, 1, 7) = ?"
    connection.execute(
        f"""
        UPDATE expenses
        SET category = ?
        WHERE LOWER(category) = LOWER(?)
          AND expense_type = 'Personale'
          AND owner = ?
          {month_clause}
        """,
        tuple(params + ([clean_month] if clean_month else [])),
    )
    if user["account_type"] == "couple" and user["couple_id"]:
        shared_params = [new_name, old_name, user["couple_id"]]
        connection.execute(
            f"""
            UPDATE expenses
            SET category = ?
            WHERE LOWER(category) = LOWER(?)
              AND expense_type = 'Condivisa'
              AND shared_couple_id = ?
              {month_clause}
            """,
            tuple(shared_params + ([clean_month] if clean_month else [])),
        )


def update_personal_category(username: str, category_id: str, name: str, color: str, icon: str) -> tuple[bool, str, dict | None]:
    clean_name = " ".join(name.strip().split())
    if not clean_name:
        return False, "Il nome della categoria non puo essere vuoto.", None
    with get_connection() as connection:
        user_id = _get_user_id_for_categories(connection, username)
        if user_id is None:
            return False, "Utente non trovato.", None
        row = connection.execute(
            "SELECT * FROM user_categories WHERE id = ? AND user_id = ? AND is_monthly_custom = 0",
            (category_id, user_id),
        ).fetchone()
        if row is None:
            return False, "Categoria non trovata.", None
        old_name = row["name"]
        normalized = _normalize_category_name(clean_name)
        duplicate = connection.execute(
            """
            SELECT id FROM user_categories
            WHERE user_id = ? AND normalized_name = ? AND is_monthly_custom = 0 AND id != ?
            """,
            (user_id, normalized, category_id),
        ).fetchone()
        if duplicate is not None:
            return False, "Questa categoria esiste gia.", None
        metadata = _default_category_metadata(clean_name)
        connection.execute(
            """
            UPDATE user_categories
            SET name = ?, normalized_name = ?, color = ?, icon = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (clean_name, normalized, color.strip() or metadata["color"], icon.strip() or metadata["icon"], category_id),
        )
        if _normalize_category_name(old_name) != normalized:
            _rename_visible_expense_category(connection, username, old_name, clean_name)
        updated = connection.execute("SELECT * FROM user_categories WHERE id = ?", (category_id,)).fetchone()
    return True, "Categoria aggiornata con successo.", _serialize_category(dict(updated)) if updated else None


def update_monthly_category(username: str, category_id: str, name: str, color: str, icon: str) -> tuple[bool, str, dict | None]:
    clean_name = " ".join(name.strip().split())
    if not clean_name:
        return False, "Il nome della categoria non puo essere vuoto.", None
    with get_connection() as connection:
        user_id = _get_user_id_for_categories(connection, username)
        if user_id is None:
            return False, "Utente non trovato.", None
        row = connection.execute(
            "SELECT * FROM user_categories WHERE id = ? AND user_id = ? AND is_monthly_custom = 1",
            (category_id, user_id),
        ).fetchone()
        if row is None:
            return False, "Categoria mensile non trovata.", None
        normalized = _normalize_category_name(clean_name)
        duplicate = connection.execute(
            """
            SELECT id FROM user_categories
            WHERE user_id = ? AND normalized_name = ? AND is_monthly_custom = 1 AND month_label = ? AND id != ?
            """,
            (user_id, normalized, row["month_label"], category_id),
        ).fetchone()
        if duplicate is not None:
            return False, "Questa categoria esiste gia nel mese selezionato.", None
        metadata = _default_category_metadata(clean_name)
        old_name = row["name"]
        connection.execute(
            """
            UPDATE user_categories
            SET name = ?, normalized_name = ?, color = ?, icon = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (clean_name, normalized, color.strip() or metadata["color"], icon.strip() or metadata["icon"], category_id),
        )
        if _normalize_category_name(old_name) != normalized:
            _rename_visible_expense_category(connection, username, old_name, clean_name, row["month_label"])
        updated = connection.execute("SELECT * FROM user_categories WHERE id = ?", (category_id,)).fetchone()
    return True, "Categoria mensile aggiornata con successo.", _serialize_category(dict(updated)) if updated else None


def delete_personal_category(username: str, category_id: str, destination_category: str = "") -> tuple[bool, str]:
    with get_connection() as connection:
        user_id = _get_user_id_for_categories(connection, username)
        if user_id is None:
            return False, "Utente non trovato."
        row = connection.execute(
            "SELECT * FROM user_categories WHERE id = ? AND user_id = ? AND is_monthly_custom = 0",
            (category_id, user_id),
        ).fetchone()
        if row is None:
            return False, "Categoria non trovata."
        if bool(row["is_default"]) or not bool(row["deletable"]):
            return False, "Non puoi eliminare una categoria di partenza."
        usage_count = _expense_usage_count_for_category(username, row["name"])
        if usage_count > 0:
            clean_destination = destination_category.strip()
            if not clean_destination:
                return False, "Scegli una categoria destinazione per redistribuire le spese."
            if _normalize_category_name(clean_destination) == _normalize_category_name(row["name"]):
                return False, "La categoria destinazione deve essere diversa."
            available = {
                _normalize_category_name(item["name"])
                for item in get_category_items(username)
                if item["id"] != category_id
            }
            if _normalize_category_name(clean_destination) not in available:
                return False, "Categoria destinazione non valida."
            _rename_visible_expense_category(connection, username, row["name"], clean_destination)
        connection.execute("DELETE FROM user_categories WHERE id = ?", (category_id,))
    return True, "Categoria eliminata con successo."


def delete_monthly_category(username: str, category_id: str) -> tuple[bool, str]:
    with get_connection() as connection:
        user_id = _get_user_id_for_categories(connection, username)
        if user_id is None:
            return False, "Utente non trovato."
        row = connection.execute(
            "SELECT * FROM user_categories WHERE id = ? AND user_id = ? AND is_monthly_custom = 1",
            (category_id, user_id),
        ).fetchone()
        if row is None:
            return False, "Categoria mensile non trovata."
        if _expense_usage_count_for_category(username, row["name"], row["month_label"]) > 0:
            return False, "Questa categoria contiene spese e non puo essere eliminata."
        connection.execute("DELETE FROM user_categories WHERE id = ?", (category_id,))
    return True, "Categoria mensile eliminata con successo."


def reset_personal_categories(username: str) -> tuple[bool, str, list[dict]]:
    ensure_user_categories(username)
    kept_used = 0
    with get_connection() as connection:
        user_id = _get_user_id_for_categories(connection, username)
        if user_id is None:
            return False, "Utente non trovato.", []
        rows = connection.execute(
            "SELECT * FROM user_categories WHERE user_id = ? AND is_monthly_custom = 0 AND is_default = 0",
            (user_id,),
        ).fetchall()
        for row in rows:
            if _expense_usage_count_for_category(username, row["name"]) > 0:
                kept_used += 1
                continue
            connection.execute("DELETE FROM user_categories WHERE id = ?", (row["id"],))
        _ensure_user_categories_for_connection(connection, user_id)
    message = "Categorie standard ripristinate."
    if kept_used:
        message = "Categorie standard ripristinate. Alcune categorie usate sono state mantenute."
    return True, message, get_personal_categories(username)


def validate_expense_data(data: dict) -> list[str]:
    """Controlla i campi obbligatori e restituisce eventuali errori."""
    errors: list[str] = []

    if data["amount"] <= 0:
        errors.append("L'importo deve essere maggiore di zero.")

    if not data["name"].strip():
        errors.append("Il nome non puo essere vuoto.")

    if data["expense_type"] == "Condivisa":
        split_type = data.get("split_type", "equal")
        split_ratio = data.get("split_ratio", 0.5)
        if split_type not in SHARED_SPLIT_OPTIONS:
            errors.append("Il tipo di divisione non e valido.")
        if split_type == "custom" and (split_ratio is None or split_ratio < 0 or split_ratio > 1):
            errors.append("La quota personalizzata deve essere tra 0% e 100%.")

    return errors


def create_expense(
    expense_date: date,
    amount: float,
    name: str,
    category: str,
    description: str,
    paid_by: str,
    expense_type: str,
    split_type: str = "equal",
    split_ratio: float = 0.5,
) -> None:
    owner = paid_by if expense_type == "Personale" else None
    shared_couple_id = None if expense_type == "Personale" else get_user_couple_id(paid_by)
    if expense_type == "Personale":
        split_type = "equal"
        split_ratio = 1.0
    with get_connection() as connection:
        connection.execute(
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
                shared_couple_id,
                split_type,
                split_ratio,
                is_settled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                expense_date.isoformat(),
                amount,
                name.strip(),
                category,
                description.strip(),
                paid_by,
                expense_type,
                owner,
                shared_couple_id,
                split_type,
                split_ratio,
                0,
            ),
        )


def validate_income_data(data: dict) -> list[str]:
    errors: list[str] = []

    if data["amount"] <= 0:
        errors.append("L'importo dell'entrata deve essere maggiore di zero.")

    if not data["source"].strip():
        errors.append("La fonte dell'entrata non puo essere vuota.")

    if not data["description"].strip():
        errors.append("La descrizione dell'entrata non puo essere vuota.")

    return errors


def create_income(
    income_date: date,
    amount: float,
    source: str,
    description: str,
    owner: str,
) -> None:
    with get_connection() as connection:
        connection.execute(
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
            (
                income_date.isoformat(),
                amount,
                source.strip(),
                description.strip(),
                owner,
            ),
        )


def update_income(
    income_id: int,
    current_username: str,
    income_date: date,
    amount: float,
    source: str,
    description: str,
) -> bool:
    if get_income_by_id(income_id, current_username) is None:
        return False
    with get_connection() as connection:
        result = connection.execute(
            """
            UPDATE incomes
            SET
                income_date = ?,
                amount = ?,
                source = ?,
                description = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                income_date.isoformat(),
                amount,
                source.strip(),
                description.strip(),
                income_id,
            ),
        )
    return result.rowcount > 0


def delete_income(income_id: int, current_username: str) -> bool:
    if get_income_by_id(income_id, current_username) is None:
        return False
    with get_connection() as connection:
        result = connection.execute("DELETE FROM incomes WHERE id = ?", (income_id,))
    return result.rowcount > 0


def update_expense(
    expense_id: int,
    current_username: str,
    expense_date: date,
    amount: float,
    name: str,
    category: str,
    description: str,
    paid_by: str,
    expense_type: str,
    split_type: str = "equal",
    split_ratio: float = 0.5,
) -> bool:
    existing_expense = get_expense_by_id(expense_id, current_username)
    if existing_expense is None:
        return False

    owner = paid_by if expense_type == "Personale" else None
    shared_couple_id = None if expense_type == "Personale" else get_user_couple_id(paid_by)
    if expense_type == "Personale":
        split_type = "equal"
        split_ratio = 1.0
    with get_connection() as connection:
        result = connection.execute(
            """
            UPDATE expenses
            SET
                expense_date = ?,
                amount = ?,
                name = ?,
                category = ?,
                description = ?,
                paid_by = ?,
                expense_type = ?,
                owner = ?,
                shared_couple_id = ?,
                split_type = ?,
                split_ratio = ?,
                is_settled = CASE WHEN ? = 'Personale' THEN 0 ELSE is_settled END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                expense_date.isoformat(),
                amount,
                name.strip(),
                category,
                description.strip(),
                paid_by,
                expense_type,
                owner,
                shared_couple_id,
                split_type,
                split_ratio,
                expense_type,
                expense_id,
            ),
        )
    return result.rowcount > 0


def delete_expense(expense_id: int, current_username: str) -> bool:
    existing_expense = get_expense_by_id(expense_id, current_username)
    if existing_expense is None:
        return False

    with get_connection() as connection:
        result = connection.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    return result.rowcount > 0


def get_expenses() -> pd.DataFrame:
    with get_connection() as connection:
        dataframe = pd.read_sql_query(
            """
            SELECT
                id,
                expense_date,
                amount,
                name,
                category,
                description,
                paid_by,
                expense_type,
                owner,
                shared_couple_id,
                split_type,
                split_ratio,
                is_settled,
                created_at,
                updated_at
            FROM expenses
            ORDER BY expense_date DESC, id DESC
            """,
            connection,
        )

    dataframe["expense_date"] = pd.to_datetime(dataframe["expense_date"])
    dataframe["month_label"] = dataframe["expense_date"].dt.strftime("%Y-%m")
    dataframe["is_settled"] = dataframe["is_settled"].fillna(0).astype(bool)
    return dataframe


def get_shared_expenses() -> pd.DataFrame:
    shared_expenses = get_expenses()
    if shared_expenses.empty:
        return shared_expenses
    return shared_expenses[shared_expenses["expense_type"] == "Condivisa"].copy()


def update_expense_settled(expense_id: int, status: bool) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE expenses
            SET
                is_settled = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (1 if status else 0, expense_id),
        )


def get_visible_expenses(dataframe: pd.DataFrame, current_username: str, current_user: dict | None = None) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()
    if current_user is not None and bool(current_user.get("is_admin")):
        return dataframe.copy()
    if current_user is None and is_admin_user(current_username):
        return dataframe.copy()
    current_user = current_user or get_user_by_username(current_username)
    if current_user is None:
        return dataframe.iloc[0:0].copy()

    personal_mask = (dataframe["expense_type"] == "Personale") & (dataframe["owner"] == current_username)
    shared_mask = False
    if current_user.get("account_type") == "couple":
        shared_mask = (dataframe["expense_type"] == "Condivisa") & (
            dataframe["shared_couple_id"].fillna("") == current_user.get("couple_id", "")
        )
    visible = dataframe[personal_mask | shared_mask].copy()
    return visible


def get_incomes() -> pd.DataFrame:
    with get_connection() as connection:
        dataframe = pd.read_sql_query(
            """
            SELECT
                id,
                income_date,
                amount,
                source,
                description,
                owner,
                created_at,
                updated_at
            FROM incomes
            ORDER BY income_date DESC, id DESC
            """,
            connection,
        )

    dataframe["income_date"] = pd.to_datetime(dataframe["income_date"])
    dataframe["month_label"] = dataframe["income_date"].dt.strftime("%Y-%m")
    return dataframe


def get_visible_incomes(dataframe: pd.DataFrame, current_username: str, current_user: dict | None = None) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()
    if current_user is not None and bool(current_user.get("is_admin")):
        return dataframe.copy()
    if current_user is None and is_admin_user(current_username):
        return dataframe.copy()
    return dataframe[dataframe["owner"] == current_username].copy()


def get_income_by_id(income_id: int, current_username: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                id,
                income_date,
                amount,
                source,
                description,
                owner,
                created_at,
                updated_at
            FROM incomes
            WHERE id = ?
            """,
            (income_id,),
        ).fetchone()

    if row is None:
        return None

    income = dict(row)
    if not _can_access_income(income, current_username):
        return None
    income["income_date"] = pd.to_datetime(income["income_date"]).date()
    return income


def apply_income_filters(dataframe: pd.DataFrame, month_label: str | None) -> pd.DataFrame:
    filtered = dataframe.copy()
    if month_label and month_label != "Tutti":
        filtered = filtered[filtered["month_label"] == month_label]
    return filtered.sort_values(by=["income_date", "id"], ascending=[False, False])


def apply_filters(
    dataframe: pd.DataFrame,
    month_label: str | None,
    category: str | None,
    payer: str | None,
    expense_type: str | None,
) -> pd.DataFrame:
    filtered = dataframe.copy()

    if month_label and month_label != "Tutti":
        filtered = filtered[filtered["month_label"] == month_label]
    if category and category != "Tutte":
        filtered = filtered[filtered["category"] == category]
    if payer and payer != "Tutti":
        filtered = filtered[filtered["paid_by"] == payer]
    if expense_type and expense_type != "Tutte":
        filtered = filtered[filtered["expense_type"] == expense_type]

    return filtered.sort_values(by=["expense_date", "id"], ascending=[False, False])


def get_user_expense_amount(row: pd.Series | dict, current_username: str, is_current_admin: bool | None = None) -> float:
    amount = float(row.get("amount", 0.0) or 0.0)
    if is_current_admin is None:
        is_current_admin = is_admin_user(current_username)
    if not current_username or is_current_admin:
        return amount
    if row.get("expense_type") != "Condivisa":
        return amount

    payer_share = _get_payer_share(pd.Series(row))
    if row.get("paid_by") == current_username:
        return amount * payer_share
    return amount * (1 - payer_share)


def compute_user_expense_total(dataframe: pd.DataFrame, current_username: str) -> float:
    if dataframe.empty:
        return 0.0
    is_current_admin = is_admin_user(current_username)
    return round(float(sum(get_user_expense_amount(row, current_username, is_current_admin) for _, row in dataframe.iterrows())), 2)


def compute_user_shared_expense_total(dataframe: pd.DataFrame, current_username: str) -> float:
    if dataframe.empty:
        return 0.0
    shared = dataframe[dataframe["expense_type"] == "Condivisa"]
    return compute_user_expense_total(shared, current_username)


def _with_user_expense_amount(dataframe: pd.DataFrame, current_username: str) -> pd.DataFrame:
    enriched = dataframe.copy()
    if enriched.empty:
        enriched["user_amount"] = []
        return enriched
    is_current_admin = is_admin_user(current_username)
    enriched["user_amount"] = [get_user_expense_amount(row, current_username, is_current_admin) for _, row in enriched.iterrows()]
    return enriched


def build_dashboard_metrics(month_dataframe: pd.DataFrame, current_username: str) -> dict:
    total_month = compute_user_expense_total(month_dataframe, current_username)

    my_personal = month_dataframe[
        (month_dataframe["expense_type"] == "Personale") & (month_dataframe["owner"] == current_username)
    ]["amount"].sum()

    shared_total = compute_user_shared_expense_total(month_dataframe, current_username)
    balance = compute_couple_balance(current_username, month_dataframe)

    return {
        "total_month": float(total_month),
        "my_personal": float(my_personal),
        "shared_total": float(shared_total),
        "balance": float(balance),
    }


def build_category_summary(dataframe: pd.DataFrame, current_username: str | None = None) -> pd.DataFrame:
    """Restituisce un riepilogo per categoria utile per la dashboard analitica."""
    if dataframe.empty:
        return pd.DataFrame()

    amount_column = "user_amount" if current_username else "amount"
    source = _with_user_expense_amount(dataframe, current_username) if current_username else dataframe.copy()
    summary = (
        source.groupby("category", as_index=False)
        .agg(
            totale=(amount_column, "sum"),
            numero_spese=("id", "count"),
        )
        .sort_values(by="totale", ascending=False)
    )

    summary["spesa_media"] = summary["totale"] / summary["numero_spese"]
    return summary


def build_income_vs_expense_summary(incomes: pd.DataFrame, expenses: pd.DataFrame, current_username: str | None = None) -> pd.DataFrame:
    income_monthly = (
        incomes.groupby("month_label", as_index=False)["amount"].sum().rename(columns={"amount": "Entrate"})
        if not incomes.empty
        else pd.DataFrame(columns=["month_label", "Entrate"])
    )
    if not expenses.empty and current_username:
        expense_source = _with_user_expense_amount(expenses, current_username)
        expense_monthly = expense_source.groupby("month_label", as_index=False)["user_amount"].sum().rename(columns={"user_amount": "Uscite"})
    else:
        expense_monthly = (
            expenses.groupby("month_label", as_index=False)["amount"].sum().rename(columns={"amount": "Uscite"})
            if not expenses.empty
            else pd.DataFrame(columns=["month_label", "Uscite"])
        )

    summary = income_monthly.merge(expense_monthly, on="month_label", how="outer").fillna(0)
    if summary.empty:
        return summary

    summary["Saldo"] = summary["Entrate"] - summary["Uscite"]
    return summary.sort_values("month_label")


def compute_balance(user1: str, user2: str, dataframe: pd.DataFrame) -> float:
    """Valore positivo: user2 deve soldi a user1. Negativo: user1 deve soldi a user2."""
    if dataframe.empty:
        return 0.0

    shared = dataframe[dataframe["expense_type"] == "Condivisa"]
    if "is_settled" in shared.columns:
        shared = shared[~shared["is_settled"].astype(bool)]
    balance = 0.0

    for _, row in shared.iterrows():
        payer_share = _get_payer_share(row)
        partner_share = float(row["amount"]) * (1 - payer_share)
        if row["paid_by"] == user1:
            balance += partner_share
        elif row["paid_by"] == user2:
            balance -= partner_share

    return round(float(balance), 2)


def compute_couple_balance(current_username: str, dataframe: pd.DataFrame | None = None) -> float:
    if not current_username:
        return 0.0

    shared_expenses = dataframe.copy() if dataframe is not None else get_shared_expenses()
    if shared_expenses.empty:
        return 0.0

    shared_expenses = shared_expenses[shared_expenses["expense_type"] == "Condivisa"].copy()
    if "is_settled" in shared_expenses.columns:
        shared_expenses = shared_expenses[~shared_expenses["is_settled"].astype(bool)]
    if shared_expenses.empty:
        return 0.0

    partner_username = get_partner_username(current_username)
    return compute_balance(current_username, partner_username, shared_expenses)


def build_couple_balance_data(
    shared_expenses: pd.DataFrame,
    current_username: str,
    *,
    month_label: str | None = "Tutti",
    year: int | None = None,
    month: int | None = None,
    status_filter: str = "open",
    category: str = "Tutte",
) -> dict:
    period = _resolve_couple_balance_period(month_label, year, month)
    period_expenses = _filter_couple_balance_period(shared_expenses, period["label"])
    period_expenses = period_expenses[period_expenses["expense_type"] == "Condivisa"].copy() if not period_expenses.empty else period_expenses.copy()
    summary_expenses = _filter_couple_balance_category(period_expenses, category)
    filtered_expenses = filter_couple_balance_expenses(summary_expenses, status_filter, "Tutte")

    return {
        "period": period,
        "status_filter": _normalize_couple_balance_status(status_filter),
        "category": category if category else "Tutte",
        "summary": _build_couple_balance_summary(summary_expenses, filtered_expenses, current_username),
        "items": [
            _build_couple_balance_item(row, current_username)
            for row in filtered_expenses.sort_values(["expense_date", "id"], ascending=[False, False]).to_dict(orient="records")
        ],
        "filters": {
            "status_options": [
                {"value": "open", "label": "Da regolare"},
                {"value": "settled", "label": "Pagate"},
                {"value": "all", "label": "Tutte"},
            ],
            "category_options": ["Tutte"] + _get_expense_categories(period_expenses),
        },
        "month_options": get_month_options(shared_expenses),
    }


def filter_couple_balance_expenses(
    dataframe: pd.DataFrame,
    status_filter: str,
    category: str = "Tutte",
) -> pd.DataFrame:
    filtered = dataframe.copy()
    normalized_status = _normalize_couple_balance_status(status_filter)

    if normalized_status == "open":
        filtered = filtered[~filtered["is_settled"].astype(bool)].copy() if not filtered.empty else filtered
    elif normalized_status == "settled":
        filtered = filtered[filtered["is_settled"].astype(bool)].copy() if not filtered.empty else filtered

    return _filter_couple_balance_category(filtered, category)


def _resolve_couple_balance_period(month_label: str | None, year: int | None, month: int | None) -> dict:
    if year is not None and month is not None:
        label = resolve_calendar_month(year=year, month=month)
    elif month_label and month_label != "Tutti":
        label = resolve_calendar_month(month_label=month_label)
    else:
        current_label = date.today().strftime("%Y-%m")
        return {
            "label": "Tutti",
            "title": "Tutti i mesi",
            "year": None,
            "month": None,
            "is_all_time": True,
            "prev_month_label": shift_calendar_month(current_label, -1),
            "next_month_label": shift_calendar_month(current_label, 1),
        }

    year_text, month_text = label.split("-")
    return {
        "label": label,
        "title": f"{CALENDAR_MONTH_NAMES.get(month_text, month_text)} {year_text}",
        "year": int(year_text),
        "month": int(month_text),
        "is_all_time": False,
        "prev_month_label": shift_calendar_month(label, -1),
        "next_month_label": shift_calendar_month(label, 1),
    }


def _filter_couple_balance_period(dataframe: pd.DataFrame, month_label: str) -> pd.DataFrame:
    if dataframe.empty or month_label == "Tutti":
        return dataframe.copy()
    return dataframe[dataframe["month_label"] == month_label].copy()


def _filter_couple_balance_category(dataframe: pd.DataFrame, category: str) -> pd.DataFrame:
    if dataframe.empty or not category or category == "Tutte":
        return dataframe.copy()
    return dataframe[dataframe["category"] == category].copy()


def _normalize_couple_balance_status(status_filter: str) -> str:
    normalized = (status_filter or "open").strip().lower()
    aliases = {
        "open": "open",
        "unsettled": "open",
        "da_regolare": "open",
        "da regolare": "open",
        "settled": "settled",
        "pagate": "settled",
        "all": "all",
        "tutte": "all",
    }
    if normalized not in aliases:
        raise ValueError("Filtro stato saldo non valido.")
    return aliases[normalized]


def _build_couple_balance_summary(summary_expenses: pd.DataFrame, filtered_expenses: pd.DataFrame, current_username: str) -> dict:
    unsettled_expenses = summary_expenses[~summary_expenses["is_settled"].astype(bool)].copy() if not summary_expenses.empty else summary_expenses
    balance = compute_couple_balance(current_username, summary_expenses)
    shared_total = float(summary_expenses["amount"].sum()) if not summary_expenses.empty else 0.0
    unsettled_total = float(unsettled_expenses["amount"].sum()) if not unsettled_expenses.empty else 0.0
    open_items = int((~summary_expenses["is_settled"].astype(bool)).sum()) if not summary_expenses.empty else 0
    settled_items = int(summary_expenses["is_settled"].astype(bool).sum()) if not summary_expenses.empty else 0

    return {
        "balance": float(balance),
        "balance_value": float(balance),
        "balance_label": _build_couple_balance_label(balance),
        "shared_total": shared_total,
        "total_shared": shared_total,
        "unsettled_total": unsettled_total,
        "total_unsettled": unsettled_total,
        "open_items": open_items,
        "settled_items": settled_items,
        "total_items": int(len(summary_expenses.index)),
        "filtered_items": int(len(filtered_expenses.index)),
    }


def _build_couple_balance_item(row: dict, current_username: str) -> dict:
    amount = float(row["amount"])
    payer_share_ratio = _get_payer_share(pd.Series(row))
    payer_share = amount * payer_share_ratio
    partner_share = amount - payer_share
    paid_by = str(row.get("paid_by") or "")
    is_current_payer = paid_by == current_username
    balance_impact = partner_share if is_current_payer else -partner_share
    status_label = "Pagata" if bool(row.get("is_settled", False)) else "Da regolare"

    return {
        "id": int(row["id"]),
        "date": _format_date_value(row.get("expense_date")),
        "expense_date": _format_date_value(row.get("expense_date")),
        "name": row.get("name", ""),
        "description": row.get("description", ""),
        "category": row.get("category", ""),
        "amount": amount,
        "paid_by": paid_by,
        "owner": row.get("owner"),
        "counterpart": get_partner_username(current_username) if current_username else "",
        "is_shared": True,
        "is_settled": bool(row.get("is_settled", False)),
        "settled": bool(row.get("is_settled", False)),
        "split_type": row.get("split_type", "equal"),
        "split_ratio": float(row.get("split_ratio", 0.5) or 0.5),
        "payer_share": float(payer_share),
        "partner_share": float(partner_share),
        "status_label": status_label,
        "action_label": "Ricevuta" if is_current_payer else "Pagata",
        "balance_impact": float(balance_impact),
        "month_label": row.get("month_label"),
    }


def _build_couple_balance_label(balance: float) -> str:
    if balance > 0:
        return "Mi devono"
    if balance < 0:
        return "Devo"
    return "Siamo in pari"


def _get_expense_categories(dataframe: pd.DataFrame) -> list[str]:
    if dataframe.empty:
        return []
    return sorted(dataframe["category"].dropna().astype(str).unique().tolist())


def _format_date_value(value: object) -> str:
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value or "")


def get_month_options(dataframe: pd.DataFrame) -> list[str]:
    current_month = date.today().strftime("%Y-%m")
    if dataframe.empty:
        return ["Tutti", current_month]

    months = dataframe["month_label"].dropna().unique().tolist()
    if current_month not in months:
        months.append(current_month)
    months = sorted(months, reverse=True)
    return ["Tutti"] + months


def resolve_calendar_month(month_label: str | None = None, year: int | None = None, month: int | None = None) -> str:
    if year is not None and month is not None:
        if month < 1 or month > 12:
            raise ValueError("Mese non valido.")
        return f"{int(year):04d}-{int(month):02d}"

    if month_label and month_label != "Tutti":
        try:
            year_text, month_text = month_label.split("-")
            resolved_year = int(year_text)
            resolved_month = int(month_text)
        except ValueError as exc:
            raise ValueError("Formato mese non valido.") from exc
        if resolved_month < 1 or resolved_month > 12:
            raise ValueError("Mese non valido.")
        return f"{resolved_year:04d}-{resolved_month:02d}"

    return date.today().strftime("%Y-%m")


def shift_calendar_month(month_label: str, delta: int) -> str:
    year_text, month_text = resolve_calendar_month(month_label).split("-")
    year = int(year_text)
    month = int(month_text) + delta

    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1

    return f"{year:04d}-{month:02d}"


def build_calendar_data(
    expenses: pd.DataFrame,
    incomes: pd.DataFrame,
    *,
    month_label: str | None = None,
    year: int | None = None,
    month: int | None = None,
    content_filter: str = "all",
    preview_limit: int = 3,
) -> dict:
    active_month_label = resolve_calendar_month(month_label, year, month)
    active_year_text, active_month_text = active_month_label.split("-")
    active_year = int(active_year_text)
    active_month = int(active_month_text)
    normalized_filter = _normalize_calendar_filter(content_filter)
    safe_preview_limit = max(0, int(preview_limit))

    month_expenses = _filter_calendar_expenses(expenses, active_month_label, normalized_filter)
    month_incomes = _filter_calendar_incomes(incomes, active_month_label, normalized_filter)
    events_by_date = _build_calendar_events_by_date(month_expenses, month_incomes)
    expense_totals = _build_daily_totals(month_expenses, "expense_date")
    income_totals = _build_daily_totals(month_incomes, "income_date")

    calendar_rows = calendar.Calendar(firstweekday=0).monthdatescalendar(active_year, active_month)
    today = date.today()
    weeks = []

    for week in calendar_rows:
        week_days = []
        for day in week:
            iso_date = day.isoformat()
            day_events = events_by_date.get(iso_date, []) if day.month == active_month else []
            expense_total = float(expense_totals.get(iso_date, 0.0)) if day.month == active_month else 0.0
            income_total = float(income_totals.get(iso_date, 0.0)) if day.month == active_month else 0.0
            week_days.append(
                {
                    "date": iso_date,
                    "day_number": day.day,
                    "is_current_month": day.month == active_month,
                    "is_today": day == today,
                    "total_expenses": expense_total,
                    "total_incomes": income_total,
                    "net_total": income_total - expense_total,
                    "events": day_events,
                    "event_count": len(day_events),
                    "preview_events": day_events[:safe_preview_limit],
                    "remaining_count": max(0, len(day_events) - safe_preview_limit),
                }
            )
        weeks.append({"days": week_days})

    return {
        "month": {
            "label": active_month_label,
            "year": active_year,
            "month": active_month,
            "title": f"{CALENDAR_MONTH_NAMES.get(active_month_text, active_month_text)} {active_year_text}",
            "prev_month_label": shift_calendar_month(active_month_label, -1),
            "next_month_label": shift_calendar_month(active_month_label, 1),
        },
        "content_filter": normalized_filter,
        "weekdays": ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"],
        "weeks": weeks,
        "summary": {
            "total_expenses": float(month_expenses["amount"].sum()) if not month_expenses.empty else 0.0,
            "total_incomes": float(month_incomes["amount"].sum()) if not month_incomes.empty else 0.0,
            "net_total": (
                float(month_incomes["amount"].sum()) if not month_incomes.empty else 0.0
            ) - (
                float(month_expenses["amount"].sum()) if not month_expenses.empty else 0.0
            ),
            "expense_count": int(len(month_expenses.index)),
            "income_count": int(len(month_incomes.index)),
            "event_count": int(len(month_expenses.index) + len(month_incomes.index)),
        },
    }


def build_calendar_day_detail(
    expenses: pd.DataFrame,
    incomes: pd.DataFrame,
    *,
    day: date,
    content_filter: str = "all",
) -> dict:
    calendar_data = build_calendar_data(
        expenses,
        incomes,
        year=day.year,
        month=day.month,
        content_filter=content_filter,
        preview_limit=10_000,
    )
    target = day.isoformat()
    for week in calendar_data["weeks"]:
        for calendar_day in week["days"]:
            if calendar_day["date"] == target:
                calendar_day["preview_events"] = calendar_day["events"]
                calendar_day["remaining_count"] = 0
                return {
                    "date": target,
                    "content_filter": calendar_data["content_filter"],
                    "day": calendar_day,
                }

    return {
        "date": target,
        "content_filter": calendar_data["content_filter"],
        "day": None,
    }


def _normalize_calendar_filter(content_filter: str) -> str:
    normalized = (content_filter or "all").strip().lower()
    aliases = {
        "tutto": "all",
        "all": "all",
        "entrate": "incomes",
        "incomes": "incomes",
        "uscite": "expenses",
        "expenses": "expenses",
    }
    if normalized not in aliases:
        raise ValueError("Filtro calendario non valido.")
    return aliases[normalized]


def _filter_calendar_expenses(dataframe: pd.DataFrame, month_label: str, content_filter: str) -> pd.DataFrame:
    if dataframe.empty or content_filter == "incomes":
        return dataframe.iloc[0:0].copy()
    return dataframe[dataframe["month_label"] == month_label].copy()


def _filter_calendar_incomes(dataframe: pd.DataFrame, month_label: str, content_filter: str) -> pd.DataFrame:
    if dataframe.empty or content_filter == "expenses":
        return dataframe.iloc[0:0].copy()
    return dataframe[dataframe["month_label"] == month_label].copy()


def _build_daily_totals(dataframe: pd.DataFrame, date_column: str) -> dict[str, float]:
    if dataframe.empty:
        return {}
    totals = dataframe.groupby(dataframe[date_column].dt.date)["amount"].sum().to_dict()
    return {day.isoformat(): float(total) for day, total in totals.items()}


def _build_calendar_events_by_date(expenses: pd.DataFrame, incomes: pd.DataFrame) -> dict[str, list[dict]]:
    events_by_date: dict[str, list[dict]] = {}

    if not expenses.empty:
        for _, row in expenses.sort_values(["expense_date", "id"]).iterrows():
            event_date = row["expense_date"].date()
            title = str(row.get("name") or row.get("description") or row.get("category") or "Spesa")
            events_by_date.setdefault(event_date.isoformat(), []).append(
                {
                    "id": int(row["id"]),
                    "type": "expense",
                    "title": title,
                    "amount": float(row["amount"]),
                    "category": row.get("category", ""),
                    "source": "",
                    "owner": row.get("owner"),
                    "paid_by": row.get("paid_by", ""),
                    "date": event_date.isoformat(),
                    "is_shared": row.get("expense_type") == "Condivisa",
                    "settled": bool(row.get("is_settled", False)),
                    "display_label": title,
                }
            )

    if not incomes.empty:
        for _, row in incomes.sort_values(["income_date", "id"]).iterrows():
            event_date = row["income_date"].date()
            title = str(row.get("source") or row.get("description") or "Entrata")
            events_by_date.setdefault(event_date.isoformat(), []).append(
                {
                    "id": int(row["id"]),
                    "type": "income",
                    "title": title,
                    "amount": float(row["amount"]),
                    "category": "",
                    "source": row.get("source", ""),
                    "owner": row.get("owner", ""),
                    "paid_by": "",
                    "date": event_date.isoformat(),
                    "is_shared": False,
                    "settled": None,
                    "display_label": title,
                }
            )

    return events_by_date


def get_expense_by_id(expense_id: int, current_username: str) -> dict | None:
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM expenses WHERE id = ?", (expense_id,)).fetchone()

    if row is None:
        return None

    expense = dict(row)
    if not _can_access_expense(expense, current_username):
        return None
    expense["expense_date"] = datetime.strptime(expense["expense_date"], "%Y-%m-%d").date()
    return expense


def export_expenses_to_csv(dataframe: pd.DataFrame) -> str:
    export_frame = dataframe.copy()
    if export_frame.empty:
        return ""

    export_frame["expense_date"] = export_frame["expense_date"].dt.strftime("%Y-%m-%d")
    export_frame = export_frame.rename(
        columns={
            "id": "ID",
            "expense_date": "Data",
            "amount": "Importo",
            "name": "Nome",
            "category": "Categoria",
            "description": "Descrizione",
            "paid_by": "Pagato da",
            "expense_type": "Tipo spesa",
            "owner": "Proprietario",
            "split_type": "Divisione",
            "split_ratio": "Quota pagatore",
        }
    )

    selected_columns = [
        "ID",
        "Data",
        "Importo",
        "Nome",
        "Categoria",
        "Descrizione",
        "Pagato da",
        "Tipo spesa",
        "Proprietario",
        "Divisione",
        "Quota pagatore",
    ]

    export_frame["Quota pagatore"] = export_frame["Quota pagatore"].apply(
        lambda value: f"{int(float(value) * 100)}%"
    )

    buffer = StringIO()
    export_frame[selected_columns].to_csv(buffer, index=False)
    return buffer.getvalue()


def export_expenses_to_pdf(dataframe: pd.DataFrame) -> bytes:
    if not REPORTLAB_AVAILABLE:
        raise ModuleNotFoundError("reportlab non installato")

    export_frame = dataframe.copy()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    if export_frame.empty:
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(40, height - 50, "Riepilogo spese")
        pdf.setFont("Helvetica", 11)
        pdf.drawString(40, height - 75, "Nessuna spesa disponibile con i filtri attivi.")
        pdf.save()
        return buffer.getvalue()

    export_frame["expense_date"] = export_frame["expense_date"].dt.strftime("%Y-%m-%d")
    export_frame = export_frame.sort_values(by=["expense_date", "id"], ascending=[False, False])

    def draw_header(page_title: str, total_count: int) -> float:
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(40, height - 45, page_title)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, height - 62, f"Totale movimenti: {total_count}")
        return height - 90

    def truncate_text(text: str, max_width: float, font_name: str = "Helvetica", font_size: int = 10) -> str:
        clean_text = str(text or "")
        if stringWidth(clean_text, font_name, font_size) <= max_width:
            return clean_text

        truncated = clean_text
        while truncated and stringWidth(f"{truncated}...", font_name, font_size) > max_width:
            truncated = truncated[:-1]
        return f"{truncated}..." if truncated else "..."

    y_position = draw_header("Riepilogo spese", len(export_frame))

    for _, row in export_frame.iterrows():
        if y_position < 100:
            pdf.showPage()
            y_position = draw_header("Riepilogo spese", len(export_frame))

        title = truncate_text(
            f"{row.get('name', '') or row.get('description', '') or 'Spesa'} - {format_currency(float(row['amount']))}",
            width - 80,
            "Helvetica-Bold",
            11,
        )
        line_one = truncate_text(
            f"{row['expense_date']} | {row['category']} | {row['paid_by']} | {row['expense_type']}",
            width - 80,
        )
        line_two = truncate_text(
            f"Tipo: {row['expense_type']} | Divisione: {_format_split_label(row)}",
            width - 80,
        )

        description = str(row.get("description") or "").strip()
        note_line = truncate_text(f"Note: {description}", width - 80) if description else ""

        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(40, y_position, title)
        y_position -= 16

        pdf.setFont("Helvetica", 10)
        pdf.drawString(40, y_position, line_one)
        y_position -= 14
        pdf.drawString(40, y_position, line_two)
        y_position -= 14

        if note_line:
            pdf.drawString(40, y_position, note_line)
            y_position -= 14

        pdf.line(40, y_position, width - 40, y_position)
        y_position -= 18

    pdf.save()
    return buffer.getvalue()


def format_currency(value: float) -> str:
    formatted_value = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"€ {formatted_value}"


def _get_payer_share(row: pd.Series) -> float:
    if row["expense_type"] != "Condivisa":
        return 1.0

    split_type = str(row.get("split_type") or "equal")
    split_ratio = row.get("split_ratio", 0.5)
    if pd.isna(split_ratio):
        split_ratio = 0.5

    if split_type == "custom":
        return float(split_ratio)
    return 0.5


def _format_split_label(row: pd.Series) -> str:
    split_type = str(row.get("split_type") or "equal")
    payer_share = _get_payer_share(row)
    partner_share = 1 - payer_share
    if split_type == "custom":
        return f"Personalizzata {int(payer_share * 100)}% / {int(partner_share * 100)}%"
    return "50/50"


def _can_access_expense(expense: dict, current_username: str) -> bool:
    if not current_username:
        return False
    if is_admin_user(current_username):
        return True
    if expense.get("expense_type") == "Personale":
        return expense.get("owner") == current_username
    current_user = get_user_by_username(current_username)
    if current_user is None or current_user.get("account_type") != "couple":
        return False
    return (expense.get("shared_couple_id") or "") == current_user.get("couple_id", "")


def _can_access_income(income: dict, current_username: str) -> bool:
    if not current_username:
        return False
    if is_admin_user(current_username):
        return True
    return income.get("owner") == current_username
