from __future__ import annotations

import hashlib
import hmac
import calendar
from datetime import date, datetime
from io import StringIO
from io import BytesIO

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
CATEGORY_OPTIONS = [
    "Spesa",
    "Casa",
    "Trasporti",
    "Ristoranti",
    "Svago",
    "Salute",
    "Abbonamenti",
    "Viaggi",
    "Regali",
    "Altro",
]
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


def authenticate_user(username: str, password: str) -> dict | None:
    """Verifica le credenziali dell'utente e restituisce i dati base se valide."""
    clean_username = username.strip().lower()
    if not clean_username:
        return None

    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, full_name, username, email, password_hash
            FROM users
            WHERE username = ?
            """,
            (clean_username,),
        ).fetchone()

    if row is None:
        return None

    password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(row["password_hash"], password_hash):
        return None

    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "username": row["username"],
        "email": row["email"] or "",
    }


def get_user_by_id(user_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, full_name, username, email
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def get_usernames() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT username FROM users ORDER BY id ASC"
        ).fetchall()
    return [row["username"] for row in rows]


def get_couple_usernames() -> tuple[str, str]:
    usernames = get_usernames()
    if len(usernames) >= 2:
        first = usernames[-2]
        second = usernames[-1]
        return first, second
    first = usernames[0] if usernames else "io"
    second = usernames[1] if len(usernames) > 1 else "compagna"
    return first, second


def get_partner_username(current_username: str) -> str:
    first, second = get_couple_usernames()
    return second if current_username == first else first


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
                "SELECT username FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if current_user is None:
                connection.rollback()
                return False, "Utente non trovato.", None

            old_username = current_user["username"]
            existing = connection.execute(
                "SELECT id FROM users WHERE LOWER(username) = LOWER(?) AND id != ?",
                (clean_username, user_id),
            ).fetchone()
            if existing is not None:
                connection.rollback()
                return False, "Questo username e gia in uso.", None

            if new_password.strip():
                connection.execute(
                    """
                    UPDATE users
                    SET full_name = ?, username = ?, email = ?, password_hash = ?
                    WHERE id = ?
                    """,
                    (clean_name, clean_username, clean_email, hashlib.sha256(new_password.encode("utf-8")).hexdigest(), user_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE users
                    SET full_name = ?, username = ?, email = ?
                    WHERE id = ?
                    """,
                    (clean_name, clean_username, clean_email, user_id),
                )

            if old_username != clean_username:
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

            connection.commit()
        except Exception:
            connection.rollback()
            raise

    updated_user = get_user_by_id(user_id)
    return True, "Profilo aggiornato con successo.", updated_user


def get_categories() -> list[str]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT name FROM categories ORDER BY LOWER(name) ASC"
        ).fetchall()
    return [row["name"] for row in rows]


def add_category(name: str) -> tuple[bool, str]:
    clean_name = name.strip()
    if not clean_name:
        return False, "Il nome della categoria non puo essere vuoto."

    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id FROM categories WHERE LOWER(name) = LOWER(?)",
            (clean_name,),
        ).fetchone()
        if existing is not None:
            return False, "Questa categoria esiste gia."

        connection.execute("INSERT INTO categories (name) VALUES (?)", (clean_name,))

    return True, "Categoria aggiunta con successo."


def delete_category(name: str) -> tuple[bool, str]:
    clean_name = name.strip()
    if not clean_name:
        return False, "Categoria non valida."

    with get_connection() as connection:
        usage = connection.execute(
            "SELECT COUNT(*) AS total FROM expenses WHERE LOWER(category) = LOWER(?)",
            (clean_name,),
        ).fetchone()
        if usage is not None and int(usage["total"]) > 0:
            return False, "Non puoi eliminare una categoria gia usata in una o piu spese."

        existing = connection.execute(
            "SELECT id FROM categories WHERE LOWER(name) = LOWER(?)",
            (clean_name,),
        ).fetchone()
        if existing is None:
            return False, "Questa categoria non esiste."

        connection.execute(
            "DELETE FROM categories WHERE LOWER(name) = LOWER(?)",
            (clean_name,),
        )

    return True, "Categoria eliminata con successo."


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
                split_type,
                split_ratio,
                is_settled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            WHERE id = ? AND owner = ?
            """,
            (
                income_date.isoformat(),
                amount,
                source.strip(),
                description.strip(),
                income_id,
                current_username,
            ),
        )
    return result.rowcount > 0


def delete_income(income_id: int, current_username: str) -> bool:
    with get_connection() as connection:
        result = connection.execute(
            "DELETE FROM incomes WHERE id = ? AND owner = ?",
            (income_id, current_username),
        )
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

    if dataframe.empty:
        return dataframe

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


def get_visible_expenses(dataframe: pd.DataFrame, current_username: str) -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()

    visible = dataframe[
        (dataframe["expense_type"] == "Condivisa") | (dataframe["owner"] == current_username)
    ].copy()
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

    if dataframe.empty:
        return dataframe

    dataframe["income_date"] = pd.to_datetime(dataframe["income_date"])
    dataframe["month_label"] = dataframe["income_date"].dt.strftime("%Y-%m")
    return dataframe


def get_visible_incomes(dataframe: pd.DataFrame, current_username: str) -> pd.DataFrame:
    if dataframe.empty:
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
            WHERE id = ? AND owner = ?
            """,
            (income_id, current_username),
        ).fetchone()

    if row is None:
        return None

    income = dict(row)
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


def build_dashboard_metrics(month_dataframe: pd.DataFrame, current_username: str) -> dict:
    total_month = float(month_dataframe["amount"].sum()) if not month_dataframe.empty else 0.0

    my_personal = month_dataframe[
        (month_dataframe["expense_type"] == "Personale") & (month_dataframe["owner"] == current_username)
    ]["amount"].sum()

    shared_total = month_dataframe[month_dataframe["expense_type"] == "Condivisa"]["amount"].sum()
    balance = compute_couple_balance(current_username, month_dataframe)

    return {
        "total_month": float(total_month),
        "my_personal": float(my_personal),
        "shared_total": float(shared_total),
        "balance": float(balance),
    }


def build_category_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Restituisce un riepilogo per categoria utile per la dashboard analitica."""
    if dataframe.empty:
        return pd.DataFrame()

    summary = (
        dataframe.groupby("category", as_index=False)
        .agg(
            totale=("amount", "sum"),
            numero_spese=("id", "count"),
        )
        .sort_values(by="totale", ascending=False)
    )

    summary["spesa_media"] = summary["totale"] / summary["numero_spese"]
    return summary


def build_income_vs_expense_summary(incomes: pd.DataFrame, expenses: pd.DataFrame) -> pd.DataFrame:
    income_monthly = (
        incomes.groupby("month_label", as_index=False)["amount"].sum().rename(columns={"amount": "Entrate"})
        if not incomes.empty
        else pd.DataFrame(columns=["month_label", "Entrate"])
    )
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
    if expense.get("expense_type") == "Personale":
        return expense.get("owner") == current_username
    return current_username in get_couple_usernames()
