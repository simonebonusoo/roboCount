from __future__ import annotations

import json
import os
import socket
import sqlite3
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import hashlib
from http.cookiejar import CookieJar
from multiprocessing import Process
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _run_server(data_dir: str, port: int) -> None:
    os.environ["MONITOR_SPESE_DATA_DIR"] = data_dir
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    import database

    base = Path(data_dir)
    database.BASE_DIR = base
    database.DATA_DIR = base / "data"
    database.DB_PATH = database.DATA_DIR / "spese.db"

    import uvicorn
    from backend.main import app

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="error")


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.cookies = CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        expected_status: int = 200,
        query: dict | None = None,
    ) -> dict:
        safe_path = urllib.parse.quote(path, safe="/?=&")
        url = f"{self.base_url}{safe_path}"
        if query:
            url = f"{url}?{urllib.parse.urlencode(query)}"

        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=10) as response:
                body = response.read().decode("utf-8")
                status = response.getcode()
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8")
            status = error.code

        if status != expected_status:
            raise AssertionError(f"{method} {path} expected {expected_status}, got {status}: {body}")
        return json.loads(body) if body else {}


def _wait_for_health(client: ApiClient) -> None:
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            payload = client.request("GET", "/api/health")
            if payload.get("status") == "ok":
                return
        except Exception:
            time.sleep(0.2)
            continue
    raise RuntimeError("Backend API did not start in time.")


def run_checks() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        port = _get_free_port()
        process = Process(target=_run_server, args=(temp_dir, port), daemon=True)
        process.start()

        base_url = f"http://127.0.0.1:{port}"
        client = ApiClient(base_url)
        try:
            _wait_for_health(client)

            client.request("GET", "/api/auth/me", expected_status=401)
            client.request("GET", "/api/profile", expected_status=401)
            client.request("GET", "/api/dashboard", expected_status=401)
            client.request("GET", "/api/expenses", expected_status=401)
            client.request("GET", "/api/incomes", expected_status=401)
            client.request("GET", "/api/categories", expected_status=401)
            client.request("GET", "/api/meta/options", expected_status=401)
            client.request("GET", "/api/couple-balance", expected_status=401)
            client.request("GET", "/api/calendar", expected_status=401)
            client.request("GET", "/api/calendar/day/2026-04-07", expected_status=401)

            admin = ApiClient(base_url)
            register = admin.request(
                "POST",
                "/api/auth/register",
                payload={
                    "full_name": "Admin One",
                    "username": "admin1",
                    "email": "admin1@example.com",
                    "password": "adminpass1",
                },
                expected_status=201,
            )
            assert register["user"]["username"] == "admin1"
            assert register["user"]["is_admin"] is True
            assert register["user"]["account_type"] == "personal"
            assert register["user"]["couple_id"] == ""

            me = admin.request("GET", "/api/auth/me")
            assert me["user"]["username"] == "admin1"
            assert me["user"]["account_type"] == "personal"

            admin.request("POST", "/api/couple-invite", expected_status=400)

            admin_partner = ApiClient(base_url)
            second_register = admin_partner.request(
                "POST",
                "/api/auth/register",
                payload={
                    "full_name": "Admin Partner",
                    "username": "admin2",
                    "email": "admin2@example.com",
                    "password": "adminpass2",
                    "account_type": "couple",
                    "avatar_id": "2",
                },
                expected_status=201,
            )
            assert second_register["user"]["is_admin"] is False
            assert second_register["user"]["couple_id"] == "admin2"
            assert second_register["user"]["couple_id"] != register["user"]["couple_id"]
            assert second_register["user"]["avatar_id"] == "2"

            invalid_invite_user = ApiClient(base_url)
            invalid_invite_user.request(
                "POST",
                "/api/auth/register",
                payload={
                    "full_name": "Invalid Invite",
                    "username": "invalidinvite",
                    "email": "invalid@example.com",
                    "password": "invalid-pass",
                    "account_type": "couple",
                    "partner_invite": "admin1",
                },
                expected_status=400,
            )

            admin.request(
                "POST",
                "/api/expenses",
                payload={
                    "expense_date": "2026-04-05",
                    "amount": 70.0,
                    "name": "Couple A Shared",
                    "category": "Casa",
                    "description": "Shared expense for couple A",
                    "paid_by": "admin1",
                    "expense_type": "Condivisa",
                    "split_type": "equal",
                    "split_ratio": 0.5,
                },
                expected_status=201,
            )
            admin_shared_id = int(admin.request("GET", "/api/expenses", query={"search": "Couple A Shared"})["items"][0]["id"])

            user_b1 = ApiClient(base_url)
            user_b1_register = user_b1.request(
                "POST",
                "/api/auth/register",
                payload={
                    "full_name": "Beta One",
                    "username": "beta1",
                    "email": "beta1@example.com",
                    "password": "betapass1",
                },
                expected_status=201,
            )
            assert user_b1_register["user"]["is_admin"] is False
            assert user_b1_register["user"]["couple_id"] == "beta1"
            beta_invite = user_b1.request("POST", "/api/couple-invite")
            assert beta_invite["invite_token"]

            user_b2 = ApiClient(base_url)
            user_b2_register = user_b2.request(
                "POST",
                "/api/auth/register",
                payload={
                    "full_name": "Beta Two",
                    "username": "beta2",
                    "email": "beta2@example.com",
                    "password": "betapass2",
                    "account_type": "couple",
                    "partner_invite": beta_invite["invite_token"],
                    "avatar_id": "8",
                },
                expected_status=201,
            )
            assert user_b2_register["user"]["account_type"] == "couple"
            assert user_b2_register["user"]["couple_id"] == user_b1_register["user"]["couple_id"]
            assert user_b2_register["user"]["couple_id"] != register["user"]["couple_id"]
            assert user_b2_register["user"]["avatar_id"] == "8"
            user_b1.request("POST", "/api/couple-invite", expected_status=400)

            third_partner = ApiClient(base_url)
            third_partner.request(
                "POST",
                "/api/auth/register",
                payload={
                    "full_name": "Beta Three",
                    "username": "beta3",
                    "email": "beta3@example.com",
                    "password": "betapass3",
                    "account_type": "couple",
                    "partner_invite": beta_invite["invite_token"],
                },
                expected_status=400,
            )

            user_b2.request("PUT", "/api/profile/avatar", payload={"avatar_id": "4"})
            assert user_b2.request("GET", "/api/auth/me")["user"]["avatar_id"] == "4"

            user_b1.request(
                "POST",
                "/api/incomes",
                payload={
                    "income_date": "2026-04-07",
                    "amount": 111.0,
                    "source": "Couple B Income",
                    "description": "Owned by beta1",
                },
                expected_status=201,
            )
            income_b_id = int(user_b1.request("GET", "/api/incomes", query={"search": "Couple B Income"})["items"][0]["id"])

            user_b1.request(
                "POST",
                "/api/expenses",
                payload={
                    "expense_date": "2026-04-07",
                    "amount": 44.0,
                    "name": "Couple B Personal",
                    "category": "Altro",
                    "description": "Personal expense owned by beta1",
                    "paid_by": "beta1",
                    "expense_type": "Personale",
                    "split_type": "equal",
                    "split_ratio": 1.0,
                },
                expected_status=201,
            )
            personal_b_id = int(user_b1.request("GET", "/api/expenses", query={"search": "Couple B Personal"})["items"][0]["id"])

            user_b1.request(
                "POST",
                "/api/expenses",
                payload={
                    "expense_date": "2026-04-08",
                    "amount": 88.5,
                    "name": "Couple B Shared",
                    "category": "Casa",
                    "description": "Shared expense for couple B",
                    "paid_by": "beta1",
                    "expense_type": "Condivisa",
                    "split_type": "custom",
                    "split_ratio": 0.6,
                },
                expected_status=201,
            )
            shared_b_id = int(user_b1.request("GET", "/api/expenses", query={"search": "Couple B Shared"})["items"][0]["id"])

            visible_for_b2 = user_b2.request("GET", "/api/expenses", query={"search": "Couple B Shared"})
            assert visible_for_b2["count"] == 1
            assert visible_for_b2["items"][0]["id"] == shared_b_id
            user_b2.request("GET", f"/api/expenses/{shared_b_id}")
            user_b2.request(
                "PUT",
                f"/api/expenses/{shared_b_id}",
                payload={
                    "expense_date": "2026-04-09",
                    "amount": 90.0,
                    "name": "Couple B Shared Updated",
                    "category": "Casa",
                    "description": "Updated by beta2",
                    "paid_by": "beta2",
                    "expense_type": "Condivisa",
                    "split_type": "equal",
                    "split_ratio": 0.5,
                },
            )
            assert user_b1.request("GET", f"/api/expenses/{shared_b_id}")["item"]["name"] == "Couple B Shared Updated"

            user_b2.request("GET", f"/api/expenses/{personal_b_id}", expected_status=404)
            user_b2.request(
                "PUT",
                f"/api/expenses/{personal_b_id}",
                payload={
                    "expense_date": "2026-04-08",
                    "amount": 50.0,
                    "name": "Blocked personal update",
                    "category": "Altro",
                    "description": "blocked",
                    "paid_by": "beta2",
                    "expense_type": "Personale",
                    "split_type": "equal",
                    "split_ratio": 1.0,
                },
                expected_status=403,
            )
            user_b2.request("DELETE", f"/api/expenses/{personal_b_id}", expected_status=403)
            user_b2.request("GET", f"/api/incomes/{income_b_id}", expected_status=404)
            user_b2.request(
                "PUT",
                f"/api/incomes/{income_b_id}",
                payload={
                    "income_date": "2026-04-08",
                    "amount": 150.0,
                    "source": "Blocked income update",
                    "description": "blocked",
                },
                expected_status=403,
            )
            user_b2.request("DELETE", f"/api/incomes/{income_b_id}", expected_status=403)
            user_b2.request("GET", f"/api/expenses/{admin_shared_id}", expected_status=404)
            user_b2.request(
                "PUT",
                f"/api/expenses/{admin_shared_id}",
                payload={
                    "expense_date": "2026-04-10",
                    "amount": 71.0,
                    "name": "Blocked foreign shared",
                    "category": "Casa",
                    "description": "blocked",
                    "paid_by": "beta2",
                    "expense_type": "Condivisa",
                    "split_type": "equal",
                    "split_ratio": 0.5,
                },
                expected_status=403,
            )
            user_b2.request("DELETE", f"/api/expenses/{admin_shared_id}", expected_status=403)

            admin_users = admin.request("GET", "/api/admin/users")
            assert len(admin_users["items"]) == 4
            admin_expenses = admin.request("GET", "/api/expenses", query={"search": "Couple B"})
            assert admin_expenses["count"] >= 2
            admin.request("GET", f"/api/incomes/{income_b_id}")
            admin.request(
                "PUT",
                f"/api/incomes/{income_b_id}",
                payload={
                    "income_date": "2026-04-10",
                    "amount": 222.0,
                    "source": "Couple B Income Updated By Admin",
                    "description": "Admin updated income",
                },
            )
            assert admin.request("GET", f"/api/incomes/{income_b_id}")["item"]["source"] == "Couple B Income Updated By Admin"
            admin.request("GET", f"/api/expenses/{personal_b_id}")
            admin.request(
                "PUT",
                f"/api/expenses/{personal_b_id}",
                payload={
                    "expense_date": "2026-04-11",
                    "amount": 55.0,
                    "name": "Couple B Personal Updated By Admin",
                    "category": "Altro",
                    "description": "Admin updated personal expense",
                    "paid_by": "beta1",
                    "expense_type": "Personale",
                    "split_type": "equal",
                    "split_ratio": 1.0,
                },
            )
            assert admin.request("GET", f"/api/expenses/{personal_b_id}")["item"]["name"] == "Couple B Personal Updated By Admin"
            admin.request(
                "PUT",
                f"/api/admin/users/{user_b2_register['user']['id']}",
                payload={
                    "full_name": "Beta Two Admin Updated",
                    "username": "beta2_admin",
                    "email": "beta2_admin@example.com",
                    "account_type": "couple",
                    "partner_invite": "",
                    "is_admin": False,
                    "new_password": "",
                },
            )
            assert user_b2.request("GET", "/api/auth/me")["user"]["username"] == "beta2_admin"
            assert user_b2.request("GET", f"/api/expenses/{shared_b_id}")["item"]["name"] == "Couple B Shared Updated"

            partner_a_primary = ApiClient(base_url)
            partner_a_secondary = ApiClient(base_url)
            partner_a_primary.request("POST", "/api/auth/login", payload={"username": "admin2", "password": "adminpass2"})
            partner_a_secondary.request("POST", "/api/auth/login", payload={"username": "admin2", "password": "adminpass2"})
            password_change = partner_a_primary.request(
                "PUT",
                "/api/profile",
                payload={
                    "full_name": "Admin Partner",
                    "username": "admin2",
                    "email": "admin2@example.com",
                    "new_password": "adminpass2-new",
                },
            )
            assert password_change["sessions_revoked"] is True
            partner_a_primary.request("GET", "/api/auth/me", expected_status=401)
            partner_a_secondary.request("GET", "/api/auth/me", expected_status=401)
            relogin_partner = ApiClient(base_url)
            relogin_partner.request("POST", "/api/auth/login", payload={"username": "admin2", "password": "adminpass2-new"})

            db_path = Path(temp_dir) / "data" / "spese.db"
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    """
                    INSERT INTO users (full_name, username, email, password_hash, is_admin, auth_version, account_type, partner_invite, couple_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Legacy User",
                        "legacy_user",
                        "legacy@example.com",
                        hashlib.sha256("legacy-pass".encode("utf-8")).hexdigest(),
                        0,
                        1,
                        "personal",
                        "",
                        "",
                    ),
                )
                connection.commit()
            legacy_client = ApiClient(base_url)
            legacy_client.request("POST", "/api/auth/login", payload={"username": "legacy_user", "password": "legacy-pass"})
            with sqlite3.connect(db_path) as connection:
                migrated_hash = connection.execute(
                    "SELECT password_hash FROM users WHERE username = ?",
                    ("legacy_user",),
                ).fetchone()[0]
            assert migrated_hash.startswith("pbkdf2_sha256$")

            rate_user = ApiClient(base_url)
            rate_user.request(
                "POST",
                "/api/auth/register",
                payload={
                    "full_name": "Rate User",
                    "username": "rateuser",
                    "email": "rate@example.com",
                    "password": "rate-pass",
                    "account_type": "personal",
                },
                expected_status=201,
            )
            rate_user.request("POST", "/api/auth/logout")
            abuser = ApiClient(base_url)
            for _ in range(5):
                abuser.request(
                    "POST",
                    "/api/auth/login",
                    payload={"username": "rateuser", "password": "wrong-pass"},
                    expected_status=401,
                )
            abuser.request(
                "POST",
                "/api/auth/login",
                payload={"username": "rateuser", "password": "wrong-pass"},
                expected_status=429,
            )

            admin.request("DELETE", f"/api/admin/users/{user_b2_register['user']['id']}")
            user_b2.request("GET", "/api/auth/me", expected_status=401)
            admin.request("GET", f"/api/expenses/{shared_b_id}", expected_status=404)

            admin.request("DELETE", f"/api/incomes/{income_b_id}")
            admin.request("DELETE", f"/api/expenses/{personal_b_id}")

            login_page_source = (PROJECT_ROOT / "frontend" / "src" / "pages" / "LoginPage.jsx").read_text(encoding="utf-8")
            assert "Codice o link invito" in login_page_source
            assert "Username della persona da invitare" not in login_page_source

            calendar_all = admin.request("GET", "/api/calendar", query={"month_label": "2026-04", "content_filter": "all"})
            assert calendar_all["month"]["label"] == "2026-04"
            assert calendar_all["month"]["prev_month_label"] == "2026-03"
            assert calendar_all["month"]["next_month_label"] == "2026-05"
            assert calendar_all["summary"]["event_count"] >= 1
            calendar_days = [day for week in calendar_all["weeks"] for day in week["days"]]
            assert any(day["date"] == "2026-03-30" and not day["is_current_month"] for day in calendar_days)

            calendar_incomes = admin.request("GET", "/api/calendar", query={"month_label": "2026-04", "content_filter": "incomes"})
            assert calendar_incomes["content_filter"] == "incomes"

            calendar_expenses = admin.request("GET", "/api/calendar", query={"year": 2026, "month": 4, "content_filter": "expenses", "preview_limit": 1})
            assert calendar_expenses["content_filter"] == "expenses"

            day_detail = admin.request("GET", "/api/calendar/day/2026-04-07")
            assert day_detail["date"] == "2026-04-07"

            dashboard = admin.request("GET", "/api/dashboard")
            assert "metrics" in dashboard

            meta = admin.request("GET", "/api/meta/options")
            assert "categories" in meta and "usernames" in meta
            assert len(meta["usernames"]) >= 4

            categories = admin.request("GET", "/api/categories")
            initial_category_count = len(categories["items"])
            admin.request("POST", "/api/categories", payload={"name": "API Test"})
            categories_after_create = admin.request("GET", "/api/categories")
            assert len(categories_after_create["items"]) == initial_category_count + 1
            admin.request("DELETE", "/api/categories/API Test")

            print("OK")
        finally:
            process.terminate()
            process.join(timeout=5)


if __name__ == "__main__":
    run_checks()
