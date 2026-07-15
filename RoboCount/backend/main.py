from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

import pandas as pd
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_runtime_config
from backend.schemas import (
    AdminUserUpdateRequest,
    AvatarUpdateRequest,
    BulkDeletePayload,
    CategoryDeletePayload,
    CategoryPayload,
    CategoryUpdatePayload,
    CalendarDayDetailResponse,
    CalendarResponse,
    CoupleBalanceResponse,
    ExpensePayload,
    IncomePayload,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
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
from database import close_pool, initialize_database
from services import (
    EXPENSE_TYPE_OPTIONS,
    SHARED_SPLIT_OPTIONS,
    add_category,
    add_personal_category,
    admin_delete_user,
    admin_update_user,
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
    compute_user_expense_total,
    compute_user_shared_expense_total,
    create_expense,
    create_income,
    create_user,
    create_couple_invite,
    delete_category,
    delete_monthly_category,
    delete_personal_category,
    delete_expense,
    delete_income,
    ensure_user_categories,
    get_categories,
    get_category_items,
    get_couple_member_details,
    get_couple_member_usernames,
    get_expense_by_id,
    get_expenses,
    get_income_by_id,
    get_incomes,
    get_month_options,
    get_partner_username,
    get_monthly_categories,
    get_personal_categories,
    get_shared_expenses,
    get_user_by_id,
    get_user_by_username,
    get_usernames,
    get_visible_expenses,
    get_visible_incomes,
    is_admin_user,
    list_users,
    reset_personal_categories,
    update_expense,
    update_expense_settled,
    update_income,
    update_monthly_category,
    update_personal_category,
    update_user_avatar,
    update_user_profile,
    validate_expense_data,
    validate_income_data,
)

SESSION_COOKIE = "monitor_spese_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30
LOGIN_RATE_LIMIT_WINDOW_SECONDS = 300
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5
LOGIN_RATE_LIMIT_BLOCK_SECONDS = 300
LOGIN_ATTEMPTS: dict[str, dict[str, float | list[float]]] = {}
RUNTIME_CONFIG = get_runtime_config(require_database=False, require_session_secret=True)


def _get_allowed_origins() -> list[str]:
    origins = {
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    }
    for item in RUNTIME_CONFIG.configured_origins:
        origins.add(item)
    vercel_url = os.getenv("VERCEL_URL", "").strip()
    if vercel_url:
        origins.add(f"https://{vercel_url}")
    return sorted(origins)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    try:
        yield
    finally:
        close_pool()


app = FastAPI(title="Monitor Spese API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_local_hostname(hostname: str | None) -> bool:
    normalized = (hostname or "").split(":", 1)[0].strip().lower()
    return normalized in {"127.0.0.1", "localhost", "::1"}


def _should_use_secure_cookie(request: Request) -> bool:
    override = RUNTIME_CONFIG.cookie_secure_override.lower()
    if override in {"1", "true", "yes", "on"}:
        return True
    if override in {"0", "false", "no", "off"}:
        return False
    forwarded_proto = request.headers.get("x-forwarded-proto", "").split(",", 1)[0].strip().lower()
    if forwarded_proto == "https":
        return True
    if _is_local_hostname(request.url.hostname):
        return False
    return request.url.scheme == "https"


def _delete_session_cookie(response: Response, request: Request) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_should_use_secure_cookie(request),
    )


def _get_session_secret() -> str:
    return RUNTIME_CONFIG.session_secret


def _encode_session_token(user: dict) -> str:
    payload = {
        "user_id": int(user["id"]),
        "auth_version": int(user.get("auth_version", 1) or 1),
        "issued_at": int(time.time()),
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_segment = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode("ascii")
    signature = hmac.new(
        _get_session_secret().encode("utf-8"),
        payload_segment.encode("ascii"),
        hashlib.sha256,
    ).digest()
    signature_segment = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return f"{payload_segment}.{signature_segment}"


def _decode_session_token(session_token: str) -> dict:
    try:
        payload_segment, signature_segment = session_token.split(".", 1)
        expected_signature = hmac.new(
            _get_session_secret().encode("utf-8"),
            payload_segment.encode("ascii"),
            hashlib.sha256,
        ).digest()
        provided_signature = base64.urlsafe_b64decode(signature_segment + "=" * (-len(signature_segment) % 4))
        if not hmac.compare_digest(expected_signature, provided_signature):
            raise ValueError("Signature mismatch")
        payload_bytes = base64.urlsafe_b64decode(payload_segment + "=" * (-len(payload_segment) % 4))
        payload = json.loads(payload_bytes.decode("utf-8"))
        if int(time.time()) - int(payload.get("issued_at", 0) or 0) > SESSION_TTL_SECONDS:
            raise ValueError("Session expired")
        return payload
    except (TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione non valida.") from None


def _set_session_cookie(response: Response, request: Request, session_token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        session_token,
        httponly=True,
        samesite="lax",
        secure=_should_use_secure_cookie(request),
        path="/",
        max_age=SESSION_TTL_SECONDS,
    )


def _invalidate_user_sessions(user_id: int) -> None:
    del user_id


def _login_rate_limit_key(request: Request, username: str) -> str:
    client_ip = request.client.host if request.client and request.client.host else "unknown"
    return f"{client_ip}:{username.strip().lower()}"


def _enforce_login_rate_limit(request: Request, username: str) -> str:
    key = _login_rate_limit_key(request, username)
    now = time.time()
    entry = LOGIN_ATTEMPTS.get(key)
    if entry is None:
        return key

    blocked_until = float(entry.get("blocked_until", 0.0) or 0.0)
    attempts = [
        timestamp
        for timestamp in entry.get("attempts", [])
        if now - float(timestamp) <= LOGIN_RATE_LIMIT_WINDOW_SECONDS
    ]
    entry["attempts"] = attempts

    if blocked_until > now:
        retry_after = max(1, int(blocked_until - now))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Troppi tentativi di accesso. Riprova tra circa {retry_after} secondi.",
        )

    entry["blocked_until"] = 0.0
    return key


def _record_failed_login_attempt(key: str) -> None:
    now = time.time()
    entry = LOGIN_ATTEMPTS.setdefault(key, {"attempts": [], "blocked_until": 0.0})
    attempts = [
        timestamp
        for timestamp in entry.get("attempts", [])
        if now - float(timestamp) <= LOGIN_RATE_LIMIT_WINDOW_SECONDS
    ]
    attempts.append(now)
    entry["attempts"] = attempts
    if len(attempts) >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
        entry["blocked_until"] = now + LOGIN_RATE_LIMIT_BLOCK_SECONDS


def _reset_login_attempts(key: str) -> None:
    LOGIN_ATTEMPTS.pop(key, None)


def get_current_user(
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict:
    if not session_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione non valida.")

    session_data = _decode_session_token(session_token)
    user = get_user_by_id(int(session_data["user_id"]))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente non disponibile.")
    if int(session_data.get("auth_version", 0)) != int(user.get("auth_version", 1)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione revocata. Accedi di nuovo.")
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


def _get_expense_category_options_for_month(current_username: str, month_label: str) -> list[str]:
    dataframe = _build_expense_frame(current_username)
    if month_label and month_label != "Tutti" and not dataframe.empty:
        dataframe = dataframe[dataframe["month_label"] == month_label]
    if dataframe.empty:
        return ["Tutte"]
    categories = sorted(
        {
            str(category).strip()
            for category in dataframe["category"].dropna().tolist()
            if str(category).strip()
        },
        key=str.lower,
    )
    return ["Tutte"] + categories


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
    total_amount = compute_user_expense_total(dataframe, current_username)
    personal_total = (
        float(dataframe[dataframe["expense_type"] == "Personale"]["amount"].sum())
        if not dataframe.empty
        else 0.0
    )
    shared_total = compute_user_shared_expense_total(dataframe, current_username)
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


def _is_personal_account(user: dict) -> bool:
    return (user.get("account_type") or "couple") == "personal"


def _ensure_valid_expense_payload(payload: ExpensePayload, current_user: dict) -> ExpensePayload:
    current_username = current_user["username"]
    paid_by = payload.paid_by
    expense_type = payload.expense_type
    if expense_type not in EXPENSE_TYPE_OPTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tipo spesa non valido.")
    if expense_type == "Personale":
        if is_admin_user(current_username):
            if paid_by not in get_usernames():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pagatore non valido.")
        else:
            paid_by = current_username
    elif paid_by not in (get_usernames() if is_admin_user(current_username) else get_couple_member_usernames(current_username)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pagatore non valido.")
    if payload.category not in get_categories(current_username, payload.expense_date):
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
def login(payload: LoginRequest, request: Request, response: Response) -> dict:
    rate_limit_key = _enforce_login_rate_limit(request, payload.username)
    user = authenticate_user(payload.username, payload.password)
    if user is None:
        _record_failed_login_attempt(rate_limit_key)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenziali non valide.")

    _reset_login_attempts(rate_limit_key)
    session_token = _encode_session_token(user)
    _set_session_cookie(response, request, session_token)
    return {"user": serialize_user(user)}


@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, response: Response) -> dict:
    success, message, user = create_user(
        full_name=payload.full_name,
        username=payload.username,
        email=payload.email,
        password=payload.password,
        account_type=payload.account_type,
        partner_invite=payload.partner_invite,
        avatar_id=payload.avatar_id,
    )
    if not success or user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

    session_token = _encode_session_token(user)
    _set_session_cookie(response, request, session_token)
    return {"message": message, "user": serialize_user(user)}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response, current_user: CurrentUser) -> dict:
    del current_user
    _delete_session_cookie(response, request)
    return {"success": True}


@app.get("/api/auth/me")
def auth_me(current_user: CurrentUser) -> dict:
    return {"user": serialize_user(current_user)}


@app.get("/api/meta/options")
def get_meta_options(current_user: CurrentUser) -> dict:
    ensure_user_categories(current_user["username"])
    if is_admin_user(current_user["username"]):
        usernames = get_usernames()
        return {
            "categories": get_categories(current_user["username"]),
            "category_items": get_category_items(current_user["username"]),
            "usernames": usernames,
            "couple_members": [serialize_user(user) for user in list_users()],
            "couple_member_count": len(usernames),
            "couple_member_limit": len(usernames),
            "expense_types": EXPENSE_TYPE_OPTIONS,
            "split_options": SHARED_SPLIT_OPTIONS,
        }
    if _is_personal_account(current_user):
        return {
            "categories": get_categories(current_user["username"]),
            "category_items": get_category_items(current_user["username"]),
            "usernames": [current_user["username"]],
            "couple_members": [serialize_user(current_user)],
            "couple_member_count": 1,
            "couple_member_limit": 1,
            "expense_types": ["Personale"],
            "split_options": ["equal"],
        }
    couple_usernames = get_couple_member_usernames(current_user["username"])
    couple_members = get_couple_member_details(current_user["username"])
    return {
        "categories": get_categories(current_user["username"]),
        "category_items": get_category_items(current_user["username"]),
        "usernames": couple_usernames,
        "couple_members": [serialize_user(user) for user in couple_members],
        "couple_member_count": len(couple_usernames),
        "couple_member_limit": 2,
        "expense_types": EXPENSE_TYPE_OPTIONS,
        "split_options": SHARED_SPLIT_OPTIONS,
    }


@app.get("/api/admin/users")
def get_admin_users(current_user: CurrentUser) -> dict:
    if not is_admin_user(current_user["username"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operazione riservata all'admin.")
    return {"items": [serialize_user(user) | {"created_at": user.get("created_at")} for user in list_users()]}


@app.put("/api/admin/users/{user_id}")
def update_admin_user(user_id: int, payload: AdminUserUpdateRequest, current_user: CurrentUser) -> dict:
    if not is_admin_user(current_user["username"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operazione riservata all'admin.")
    success, message, updated_user, password_changed = admin_update_user(
        user_id=user_id,
        full_name=payload.full_name,
        username=payload.username,
        email=payload.email,
        account_type=payload.account_type,
        partner_invite=payload.partner_invite,
        is_admin=payload.is_admin,
        new_password=payload.new_password,
    )
    if not success or updated_user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    if password_changed:
        _invalidate_user_sessions(user_id)
    return {
        "message": message,
        "user": serialize_user(updated_user),
        "password_changed": password_changed,
    }


@app.delete("/api/admin/users/{user_id}")
def delete_admin_user(user_id: int, current_user: CurrentUser) -> dict:
    if not is_admin_user(current_user["username"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Operazione riservata all'admin.")
    success, message = admin_delete_user(user_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    _invalidate_user_sessions(user_id)
    return {"message": message}


@app.get("/api/profile")
def get_profile(current_user: CurrentUser) -> dict:
    return {"user": serialize_user(current_user)}


@app.get("/api/profile/categories")
def get_profile_categories(current_user: CurrentUser, month_label: str = "") -> dict:
    effective_month = month_label or date.today().strftime("%Y-%m")
    defaults = get_personal_categories(current_user["username"])
    monthly = get_monthly_categories(current_user["username"], effective_month)
    return {"items": defaults, "defaults": defaults, "monthly": monthly, "month_label": effective_month}


@app.post("/api/profile/categories")
def create_profile_category(payload: CategoryPayload, current_user: CurrentUser) -> dict:
    success, message, category = add_personal_category(current_user["username"], payload.name, payload.color, payload.icon)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "category": category}


@app.put("/api/profile/categories/{category_id}")
def edit_profile_category(category_id: str, payload: CategoryUpdatePayload, current_user: CurrentUser) -> dict:
    success, message, category = update_personal_category(
        current_user["username"],
        category_id,
        payload.name,
        payload.color,
        payload.icon,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "category": category}


@app.delete("/api/profile/categories/{category_id}")
def remove_profile_category(category_id: str, current_user: CurrentUser) -> dict:
    success, message = delete_personal_category(current_user["username"], category_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}


@app.post("/api/profile/categories/{category_id}/delete")
def remove_profile_category_with_payload(category_id: str, payload: CategoryDeletePayload, current_user: CurrentUser) -> dict:
    success, message = delete_personal_category(current_user["username"], category_id, payload.destination_category)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}


@app.post("/api/profile/monthly-categories")
def create_profile_monthly_category(payload: CategoryPayload, current_user: CurrentUser) -> dict:
    effective_month = payload.month_label or date.today().strftime("%Y-%m")
    success, message, category = add_category(
        payload.name,
        current_user["username"],
        effective_month,
        payload.color,
        payload.icon,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "category": category}


@app.put("/api/profile/monthly-categories/{category_id}")
def edit_profile_monthly_category(category_id: str, payload: CategoryUpdatePayload, current_user: CurrentUser) -> dict:
    success, message, category = update_monthly_category(
        current_user["username"],
        category_id,
        payload.name,
        payload.color,
        payload.icon,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "category": category}


@app.delete("/api/profile/monthly-categories/{category_id}")
def remove_profile_monthly_category(category_id: str, current_user: CurrentUser) -> dict:
    success, message = delete_monthly_category(current_user["username"], category_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message}


@app.post("/api/profile/categories/reset")
def reset_profile_categories(current_user: CurrentUser) -> dict:
    success, message, items = reset_personal_categories(current_user["username"])
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "items": items}


@app.post("/api/couple-invite")
def create_partner_invite(current_user: CurrentUser, request: Request) -> dict:
    success, message, invite = create_couple_invite(current_user["username"])
    if not success or invite is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    invite_url = str(request.url_for("register_via_invite")).split("?", 1)[0] + "?mode=register&type=couple&invite_token=" + invite["invite_token"]
    return {"message": message, "invite_token": invite["invite_token"], "invite_url": invite_url}


@app.get("/login", include_in_schema=False, name="register_via_invite")
def register_via_invite_placeholder() -> dict:
    return {"detail": "Frontend route"}


@app.put("/api/profile/avatar")
def update_profile_avatar(payload: AvatarUpdateRequest, current_user: CurrentUser) -> dict:
    success, message, updated_user = update_user_avatar(current_user["id"], payload.avatar_id)
    if not success or updated_user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "user": serialize_user(updated_user), "sessions_revoked": False}


@app.put("/api/profile")
def update_profile(payload: ProfileUpdateRequest, current_user: CurrentUser) -> dict:
    password_changed = bool(payload.new_password.strip())
    success, message, updated_user = update_user_profile(
        user_id=current_user["id"],
        full_name=payload.full_name,
        username=payload.username,
        email=payload.email,
        new_password=payload.new_password,
    )
    if not success or updated_user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    if password_changed:
        _invalidate_user_sessions(current_user["id"])
    return {
        "message": message,
        "user": serialize_user(updated_user),
        "password_changed": password_changed,
        "sessions_revoked": password_changed,
    }


@app.get("/api/categories")
def list_categories(current_user: CurrentUser, month_label: str = "") -> dict:
    effective_month_label = month_label or date.today().strftime("%Y-%m")
    category_items = get_category_items(current_user["username"], effective_month_label)
    return {"items": [item["name"] for item in category_items], "category_items": category_items}


@app.post("/api/categories")
def create_category(payload: CategoryPayload, current_user: CurrentUser) -> dict:
    success, message, category = add_category(
        payload.name,
        current_user["username"],
        payload.month_label or date.today().strftime("%Y-%m"),
        payload.color,
        payload.icon,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
    return {"message": message, "category": category}


@app.delete("/api/categories/{category_name}")
def remove_category(category_name: str, current_user: CurrentUser, month_label: str = "") -> dict:
    success, message = delete_category(category_name, current_user["username"], month_label or date.today().strftime("%Y-%m"))
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
    category_summary = build_category_summary(filtered_expenses, current_username)
    income_expense_summary = build_income_vs_expense_summary(incomes, expenses, current_username)

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
            "category_options": _get_expense_category_options_for_month(current_username, month_label),
            "payer_options": ["Tutti"] + (get_usernames() if is_admin_user(current_username) else get_couple_member_usernames(current_username)),
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
    if not is_admin_user(current_username) and _is_personal_account(current_user) and payload.expense_type != "Personale":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Le spese condivise sono disponibili solo negli account coppia.")
    valid_payload = _ensure_valid_expense_payload(payload, current_user)
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
    if not is_admin_user(current_username) and _is_personal_account(current_user) and payload.expense_type != "Personale":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Le spese condivise sono disponibili solo negli account coppia.")
    valid_payload = _ensure_valid_expense_payload(payload, current_user)
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
    if _is_personal_account(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Il saldo di coppia non e disponibile per account personali.")
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
    if _is_personal_account(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Il saldo di coppia non e disponibile per account personali.")
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
    if _is_personal_account(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Il saldo di coppia non e disponibile per account personali.")
    expense = get_expense_by_id(expense_id, current_user["username"])
    if expense is None or expense.get("expense_type") != "Condivisa":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spesa condivisa non trovata.")
    update_expense_settled(expense_id, payload.is_settled)
    return {"message": "Stato saldo aggiornato con successo."}
