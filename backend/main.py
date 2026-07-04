from __future__ import annotations

import os
import secrets
from datetime import date
from typing import Annotated

import pandas as pd
from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware

from backend.schemas import (
    BulkDeletePayload,
    CategoryPayload,
    CalendarDayDetailResponse,
    CalendarResponse,
    CoupleBalanceResponse,
    ExpensePayload,
    IncomePayload,
    LoginRequest,
    ProfileUpdateRequest,
    SettledPayload,
)
from backend.serializers import (
    serialize_category_summary,
    serialize_expense,
    serialize_expense_frame,
    serialize_income,
    serialize_income_expense_summary,
    serialize_income_frame,
    serialize_metrics,
    serialize_user,
)
from database import initialize_database
from services import (
    EXPENSE_TYPE_OPTIONS,
    SHARED_SPLIT_OPTIONS,
    add_category,
    apply_filters,
    apply_income_filters,
    authenticate_user,
    build_category_summary,
    build_calendar_data,
    build_calendar_day_detail,
    build_couple_balance_data,
    build_dashboard_metrics,
    build_income_vs_expense_summary,
    compute_balance,
    create_expense,
    create_income,
    delete_category,
    delete_expense,
    delete_income,
    get_categories,
    get_couple_usernames,
    get_expense_by_id,
    get_expenses,
    get_income_by_id,
    get_incomes,
    get_month_options,
    get_partner_username,
    get_shared_expenses,
    get_user_by_id,
    get_usernames,
    get_visible_expenses,
    get_visible_incomes,
    update_expense,
    update_expense_settled,
    update_income,
    update_user_profile,
    validate_expense_data,
    validate_income_data,
)


SESSION_COOKIE = "monitor_spese_session"
SESSION_STORE: dict[str, int] = {}
origins = [
    "http://127.0.0.1:5173",
    "http://localhost:5173",
]

app = FastAPI(title="Monitor Spese API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    initialize_database()


def get_current_user(
    session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict:
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione non valida.")

    user_id = SESSION_STORE.get(session_id)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione scaduta.")

    user = get_user_by_id(user_id)
    if user is None:
        SESSION_STORE.pop(session_id, None)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente non disponibile.")
    return user


CurrentUser = Annotated[dict, Depends(get_current_user)]


def _build_expense_frame(current_username: str) -> pd.DataFrame:
    return get_visible_expenses(get_expenses(), current_username)


def _build_income_frame(current_username: str) -> pd.DataFrame:
    return get_visible_incomes(get_incomes(), current_username)


def _filter_expenses(
    current_username: str,
    month_label: str = "Tutti",
    category: str = "Tutte",
    payer: str = "Tutti",
    expense_type: str = "Tutte",
    search: str = "",
) -> pd.DataFrame:
    dataframe = _build_expense_frame(current_username)
    filtered = apply_filters(dataframe, month_label, category, payer, expense_type)
    if search.strip():
        normalized = search.strip().lower()
        search_frame = filtered.fillna("")
        mask = (
            search_frame["name"].str.lower().str.contains(normalized)
            | search_frame["description"].str.lower().str.contains(normalized)
            | search_frame["category"].str.lower().str.contains(normalized)
            | search_frame["paid_by"].str.lower().str.contains(normalized)
        )
        filtered = filtered[mask]
    return filtered.copy()


def _sort_expenses(dataframe: pd.DataFrame, sort: str = "date_desc") -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()
    if sort == "amount_desc":
        return dataframe.sort_values(by=["amount", "expense_date", "id"], ascending=[False, False, False]).copy()
    if sort == "amount_asc":
        return dataframe.sort_values(by=["amount", "expense_date", "id"], ascending=[True, False, False]).copy()
    return dataframe.sort_values(by=["expense_date", "id"], ascending=[False, False]).copy()


def _sort_incomes(dataframe: pd.DataFrame, sort: str = "date_desc") -> pd.DataFrame:
    if dataframe.empty:
        return dataframe.copy()
    if sort == "amount_desc":
        return dataframe.sort_values(by=["amount", "income_date", "id"], ascending=[False, False, False]).copy()
    if sort == "amount_asc":
        return dataframe.sort_values(by=["amount", "income_date", "id"], ascending=[True, False, False]).copy()
    return dataframe.sort_values(by=["income_date", "id"], ascending=[False, False]).copy()


def _filter_incomes(
    current_username: str,
    month_label: str = "Tutti",
    search: str = "",
) -> pd.DataFrame:
    dataframe = _build_income_frame(current_username)
    filtered = apply_income_filters(dataframe, month_label)
    if search.strip():
        normalized = search.strip().lower()
        search_frame = filtered.fillna("")
        mask = (
            search_frame["source"].str.lower().str.contains(normalized)
            | search_frame["description"].str.lower().str.contains(normalized)
        )
        filtered = filtered[mask]
    return filtered.copy()


def _build_expense_list_summary(dataframe: pd.DataFrame, current_username: str) -> dict:
    total_amount = float(dataframe["amount"].sum()) if not dataframe.empty else 0.0
    personal_total = (
        float(dataframe[dataframe["expense_type"] == "Personale"]["amount"].sum())
        if not dataframe.empty
        else 0.0
    )
    shared_total = (
        float(dataframe[dataframe["expense_type"] == "Condivisa"]["amount"].sum())
        if not dataframe.empty
        else 0.0
    )
    balance = compute_balance(current_username, get_partner_username(current_username), dataframe) if current_username else 0.0
    return {
        "total_amount": total_amount,
        "personal_total": personal_total,
        "shared_total": shared_total,
        "balance": float(balance),
        "count": int(len(dataframe.index)),
    }


def _build_income_list_summary(dataframe: pd.DataFrame) -> dict:
    top_source = ""
    if not dataframe.empty:
        grouped = dataframe.groupby("source")["amount"].sum().sort_values(ascending=False)
        top_source = str(grouped.index[0]) if not grouped.empty else ""
    return {
        "total_amount": float(dataframe["amount"].sum()) if not dataframe.empty else 0.0,
        "count": int(len(dataframe.index)),
        "top_source": top_source,
    }


def _ensure_valid_expense_payload(payload: ExpensePayload, current_username: str) -> ExpensePayload:
    paid_by = payload.paid_by
    expense_type = payload.expense_type
    if expense_type not in EXPENSE_TYPE_OPTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo spesa non valido.")
    if expense_type == "Personale":
        paid_by = current_username
    elif paid_by not in get_couple_usernames():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pagatore non valido.")
    if payload.category not in get_categories():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Categoria non valida.")

    validated_payload = ExpensePayload(
        expense_date=payload.expense_date,
        amount=payload.amount,
        name=payload.name,
        category=payload.category,
        description=payload.description,
        paid_by=paid_by,
        expense_type=expense_type,
        split_type=payload.split_type,
        split_ratio=payload.split_ratio,
    )
    errors = validate_expense_data(validated_payload.model_dump())
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)
    return validated_payload


def _ensure_valid_income_payload(payload: IncomePayload) -> None:
    errors = validate_income_data(payload.model_dump())
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=errors)


@app.get("/api/health")
def healthcheck() -> dict:
    return {"status": "ok"}


@app.post("/api/auth/login")
def login(payload: LoginRequest, response: Response) -> dict:
    user = authenticate_user(payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenziali non valide.")

    session_id = secrets.token_urlsafe(32)
    SESSION_STORE[session_id] = user["id"]
    response.set_cookie(
        SESSION_COOKIE,
        session_id,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return {"user": serialize_user(user)}


@app.post("/api/auth/logout")
def logout(response: Response, current_user: CurrentUser, session_id: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None) -> dict:
    del current_user
    if session_id:
        SESSION_STORE.pop(session_id, None)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"success": True}


@app.get("/api/auth/me")
def auth_me(current_user: CurrentUser) -> dict:
    return {"user": serialize_user(current_user)}


@app.get("/api/meta/options")
def get_meta_options(current_user: CurrentUser) -> dict:
    del current_user
    return {
        "categories": get_categories(),
        "usernames": list(get_couple_usernames()),
        "expense_types": EXPENSE_TYPE_OPTIONS,
        "split_options": SHARED_SPLIT_OPTIONS,
    }


@app.get("/api/profile")
def get_profile(current_user: CurrentUser) -> dict:
    return {"user": serialize_user(current_user)}


@app.put("/api/profile")
def update_profile(payload: ProfileUpdateRequest, current_user: CurrentUser) -> dict:
    success, message, updated_user = update_user_profile(
        user_id=current_user["id"],
        full_name=payload.full_name,
        username=payload.username,
        email=payload.email,
        new_password=payload.new_password,
    )
    if not success or updated_user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "user": serialize_user(updated_user)}


@app.get("/api/categories")
def list_categories(current_user: CurrentUser) -> dict:
    del current_user
    return {"items": get_categories()}


@app.post("/api/categories")
def create_category(payload: CategoryPayload, current_user: CurrentUser) -> dict:
    del current_user
    success, message = add_category(payload.name)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}


@app.delete("/api/categories/{category_name}")
def remove_category(category_name: str, current_user: CurrentUser) -> dict:
    del current_user
    success, message = delete_category(category_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}


@app.get("/api/dashboard")
def get_dashboard(current_user: CurrentUser, month_label: str = "Tutti") -> dict:
    current_username = current_user["username"]
    expenses = _build_expense_frame(current_username)
    incomes = _build_income_frame(current_username)
    filtered_expenses = apply_filters(expenses, month_label, "Tutte", "Tutti", "Tutte")
    filtered_incomes = apply_income_filters(incomes, month_label)
    metrics = build_dashboard_metrics(filtered_expenses, current_username)
    category_summary = build_category_summary(filtered_expenses)
    income_expense_summary = build_income_vs_expense_summary(incomes, expenses)

    month_options = sorted(set(get_month_options(expenses) + get_month_options(incomes)), reverse=False)
    if "Tutti" in month_options:
        month_options = ["Tutti"] + sorted([item for item in month_options if item != "Tutti"], reverse=True)

    return {
        "selected_month": month_label,
        "month_options": month_options,
        "metrics": serialize_metrics(metrics),
        "category_summary": serialize_category_summary(category_summary),
        "income_expense_summary": serialize_income_expense_summary(income_expense_summary),
        "recent_expenses": serialize_expense_frame(filtered_expenses.head(8)),
        "recent_incomes": serialize_income_frame(filtered_incomes.head(8)),
    }


@app.get("/api/calendar", response_model=CalendarResponse)
def get_calendar(
    current_user: CurrentUser,
    month_label: str | None = None,
    year: int | None = None,
    month: int | None = None,
    content_filter: str = "all",
    preview_limit: int = 3,
) -> dict:
    current_username = current_user["username"]
    try:
        return build_calendar_data(
            _build_expense_frame(current_username),
            _build_income_frame(current_username),
            month_label=month_label,
            year=year,
            month=month,
            content_filter=content_filter,
            preview_limit=preview_limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.get("/api/calendar/day/{date_value}", response_model=CalendarDayDetailResponse)
def get_calendar_day(date_value: date, current_user: CurrentUser, content_filter: str = "all") -> dict:
    current_username = current_user["username"]
    try:
        return build_calendar_day_detail(
            _build_expense_frame(current_username),
            _build_income_frame(current_username),
            day=date_value,
            content_filter=content_filter,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.get("/api/expenses")
def list_expenses(
    current_user: CurrentUser,
    month_label: str = "Tutti",
    category: str = "Tutte",
    payer: str = "Tutti",
    expense_type: str = "Tutte",
    search: str = "",
    sort: str = "date_desc",
) -> dict:
    current_username = current_user["username"]
    filtered = _filter_expenses(current_username, month_label, category, payer, expense_type, search)
    filtered = _sort_expenses(filtered, sort)
    return {
        "items": serialize_expense_frame(filtered),
        "count": int(len(filtered.index)),
        "summary": _build_expense_list_summary(filtered, current_username),
        "month_options": get_month_options(_build_expense_frame(current_username)),
        "filters": {
            "category_options": ["Tutte"] + get_categories(),
            "payer_options": ["Tutti"] + list(get_couple_usernames()),
            "expense_type_options": ["Tutte"] + EXPENSE_TYPE_OPTIONS,
            "sort_options": [
                {"value": "date_desc", "label": "Data piu recente"},
                {"value": "amount_desc", "label": "Importo maggiore"},
                {"value": "amount_asc", "label": "Importo minore"},
            ],
        },
    }


@app.post("/api/expenses/bulk-delete")
def bulk_delete_expenses(payload: BulkDeletePayload, current_user: CurrentUser) -> dict:
    deleted_ids = []
    skipped_ids = []
    for expense_id in payload.ids:
        if delete_expense(int(expense_id), current_user["username"]):
            deleted_ids.append(int(expense_id))
        else:
            skipped_ids.append(int(expense_id))
    return {
        "message": "Spese eliminate con successo." if deleted_ids else "Nessuna spesa eliminata.",
        "deleted_ids": deleted_ids,
        "skipped_ids": skipped_ids,
        "deleted_count": len(deleted_ids),
        "skipped_count": len(skipped_ids),
    }


@app.get("/api/expenses/{expense_id}")
def expense_detail(expense_id: int, current_user: CurrentUser) -> dict:
    expense = get_expense_by_id(expense_id, current_user["username"])
    if expense is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spesa non trovata.")
    return {"item": serialize_expense(expense)}


@app.post("/api/expenses", status_code=status.HTTP_201_CREATED)
def create_expense_endpoint(payload: ExpensePayload, current_user: CurrentUser) -> dict:
    current_username = current_user["username"]
    valid_payload = _ensure_valid_expense_payload(payload, current_username)
    create_expense(
        expense_date=valid_payload.expense_date,
        amount=valid_payload.amount,
        name=valid_payload.name,
        category=valid_payload.category,
        description=valid_payload.description,
        paid_by=valid_payload.paid_by,
        expense_type=valid_payload.expense_type,
        split_type=valid_payload.split_type,
        split_ratio=valid_payload.split_ratio,
    )
    return {"message": "Spesa creata con successo."}


@app.put("/api/expenses/{expense_id}")
def update_expense_endpoint(expense_id: int, payload: ExpensePayload, current_user: CurrentUser) -> dict:
    current_username = current_user["username"]
    valid_payload = _ensure_valid_expense_payload(payload, current_username)
    updated = update_expense(
        expense_id=expense_id,
        current_username=current_username,
        expense_date=valid_payload.expense_date,
        amount=valid_payload.amount,
        name=valid_payload.name,
        category=valid_payload.category,
        description=valid_payload.description,
        paid_by=valid_payload.paid_by,
        expense_type=valid_payload.expense_type,
        split_type=valid_payload.split_type,
        split_ratio=valid_payload.split_ratio,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operazione non autorizzata.")
    return {"message": "Spesa aggiornata con successo."}


@app.delete("/api/expenses/{expense_id}")
def delete_expense_endpoint(expense_id: int, current_user: CurrentUser) -> dict:
    deleted = delete_expense(expense_id, current_user["username"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operazione non autorizzata.")
    return {"message": "Spesa eliminata con successo."}


@app.patch("/api/expenses/{expense_id}/settled")
def update_expense_settled_endpoint(expense_id: int, payload: SettledPayload, current_user: CurrentUser) -> dict:
    expense = get_expense_by_id(expense_id, current_user["username"])
    if expense is None or expense.get("expense_type") != "Condivisa":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spesa condivisa non trovata.")
    update_expense_settled(expense_id, payload.is_settled)
    return {"message": "Stato aggiornato con successo."}


@app.get("/api/incomes")
def list_incomes(
    current_user: CurrentUser,
    month_label: str = "Tutti",
    search: str = "",
    sort: str = "date_desc",
) -> dict:
    current_username = current_user["username"]
    filtered = _filter_incomes(current_username, month_label, search)
    filtered = _sort_incomes(filtered, sort)
    return {
        "items": serialize_income_frame(filtered),
        "count": int(len(filtered.index)),
        "summary": _build_income_list_summary(filtered),
        "month_options": get_month_options(_build_income_frame(current_username)),
        "filters": {
            "sort_options": [
                {"value": "date_desc", "label": "Data piu recente"},
                {"value": "amount_desc", "label": "Importo maggiore"},
                {"value": "amount_asc", "label": "Importo minore"},
            ],
        },
    }


@app.get("/api/incomes/{income_id}")
def income_detail(income_id: int, current_user: CurrentUser) -> dict:
    income = get_income_by_id(income_id, current_user["username"])
    if income is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrata non trovata.")
    return {"item": serialize_income(income)}


@app.post("/api/incomes", status_code=status.HTTP_201_CREATED)
def create_income_endpoint(payload: IncomePayload, current_user: CurrentUser) -> dict:
    _ensure_valid_income_payload(payload)
    create_income(
        income_date=payload.income_date,
        amount=payload.amount,
        source=payload.source,
        description=payload.description,
        owner=current_user["username"],
    )
    return {"message": "Entrata creata con successo."}


@app.put("/api/incomes/{income_id}")
def update_income_endpoint(income_id: int, payload: IncomePayload, current_user: CurrentUser) -> dict:
    _ensure_valid_income_payload(payload)
    updated = update_income(
        income_id=income_id,
        current_username=current_user["username"],
        income_date=payload.income_date,
        amount=payload.amount,
        source=payload.source,
        description=payload.description,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operazione non autorizzata.")
    return {"message": "Entrata aggiornata con successo."}


@app.delete("/api/incomes/{income_id}")
def delete_income_endpoint(income_id: int, current_user: CurrentUser) -> dict:
    deleted = delete_income(income_id, current_user["username"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operazione non autorizzata.")
    return {"message": "Entrata eliminata con successo."}


@app.get("/api/couple-balance", response_model=CoupleBalanceResponse)
def get_couple_balance_view(
    current_user: CurrentUser,
    month_label: str = "Tutti",
    year: int | None = None,
    month: int | None = None,
    status_filter: str = "all",
    category: str = "Tutte",
) -> CoupleBalanceResponse:
    current_username = current_user["username"]
    shared = get_shared_expenses()
    shared = get_visible_expenses(shared, current_username)
    try:
        return build_couple_balance_data(
            shared,
            current_username,
            month_label=month_label,
            year=year,
            month=month,
            status_filter=status_filter,
            category=category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.patch("/api/couple-balance/{expense_id}/settled")
def update_couple_balance_settled(expense_id: int, payload: SettledPayload, current_user: CurrentUser) -> dict:
    expense = get_expense_by_id(expense_id, current_user["username"])
    if expense is None or expense.get("expense_type") != "Condivisa":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spesa condivisa non trovata.")
    update_expense_settled(expense_id, payload.is_settled)
    return {"message": "Stato saldo aggiornato con successo."}
