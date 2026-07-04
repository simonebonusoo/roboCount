from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from services import compute_couple_balance


def serialize_user(user: dict | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": user["id"],
        "full_name": user.get("full_name", ""),
        "username": user.get("username", ""),
        "email": user.get("email", ""),
    }


def serialize_expense(expense: dict) -> dict:
    return {
        "id": int(expense["id"]),
        "expense_date": _format_value(expense.get("expense_date")),
        "amount": float(expense["amount"]),
        "name": expense.get("name", ""),
        "category": expense.get("category", ""),
        "description": expense.get("description", ""),
        "paid_by": expense.get("paid_by", ""),
        "expense_type": expense.get("expense_type", ""),
        "owner": expense.get("owner"),
        "split_type": expense.get("split_type", "equal"),
        "split_ratio": float(expense.get("split_ratio", 0.5) or 0.5),
        "is_settled": bool(expense.get("is_settled", False)),
        "month_label": expense.get("month_label"),
        "created_at": expense.get("created_at"),
        "updated_at": expense.get("updated_at"),
    }


def serialize_income(income: dict) -> dict:
    return {
        "id": int(income["id"]),
        "income_date": _format_value(income.get("income_date")),
        "amount": float(income["amount"]),
        "source": income.get("source", ""),
        "description": income.get("description", ""),
        "owner": income.get("owner", ""),
        "month_label": income.get("month_label"),
        "created_at": income.get("created_at"),
        "updated_at": income.get("updated_at"),
    }


def serialize_expense_frame(dataframe: pd.DataFrame) -> list[dict]:
    if dataframe.empty:
        return []
    return [serialize_expense(row) for row in dataframe.to_dict(orient="records")]


def serialize_income_frame(dataframe: pd.DataFrame) -> list[dict]:
    if dataframe.empty:
        return []
    return [serialize_income(row) for row in dataframe.to_dict(orient="records")]


def serialize_category_summary(dataframe: pd.DataFrame) -> list[dict]:
    if dataframe.empty:
        return []
    records = []
    for row in dataframe.to_dict(orient="records"):
        records.append(
            {
                "category": row["category"],
                "totale": float(row["totale"]),
                "numero_spese": int(row["numero_spese"]),
                "spesa_media": float(row["spesa_media"]),
            }
        )
    return records


def serialize_income_expense_summary(dataframe: pd.DataFrame) -> list[dict]:
    if dataframe.empty:
        return []
    records = []
    for row in dataframe.to_dict(orient="records"):
        records.append(
            {
                "month_label": row["month_label"],
                "entrate": float(row["Entrate"]),
                "uscite": float(row["Uscite"]),
                "saldo": float(row["Saldo"]),
            }
        )
    return records


def serialize_metrics(metrics: dict) -> dict:
    return {
        "total_month": float(metrics.get("total_month", 0.0)),
        "my_personal": float(metrics.get("my_personal", 0.0)),
        "shared_total": float(metrics.get("shared_total", 0.0)),
        "balance": float(metrics.get("balance", 0.0)),
    }


def serialize_couple_balance(dataframe: pd.DataFrame, current_username: str) -> dict:
    total_balance = compute_couple_balance(current_username, dataframe)
    shared_total = float(dataframe["amount"].sum()) if not dataframe.empty else 0.0
    return {
        "balance": total_balance,
        "shared_total": shared_total,
        "open_items": int((~dataframe["is_settled"].astype(bool)).sum()) if not dataframe.empty else 0,
        "total_items": int(len(dataframe.index)) if not dataframe.empty else 0,
    }


def _format_value(value: object) -> object:
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value

