from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
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

        client = ApiClient(f"http://127.0.0.1:{port}")
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
            login = client.request(
                "POST",
                "/api/auth/login",
                payload={"username": "io", "password": ""},
            )
            assert login["user"]["username"] == "io"

            me = client.request("GET", "/api/auth/me")
            assert me["user"]["username"] == "io"

            profile = client.request("GET", "/api/profile")
            assert profile["user"]["username"] == "io"

            updated_profile = client.request(
                "PUT",
                "/api/profile",
                payload={
                    "full_name": "Nuovo Nome API",
                    "username": "mattia_api",
                    "email": "api@example.com",
                    "new_password": "secret123",
                },
            )
            assert updated_profile["user"]["username"] == "mattia_api"

            me_after_profile = client.request("GET", "/api/auth/me")
            assert me_after_profile["user"]["username"] == "mattia_api"

            client.request(
                "POST",
                "/api/incomes",
                payload={
                    "income_date": "2026-04-07",
                    "amount": 111.0,
                    "source": "Income Ownership",
                    "description": "Income ownership check",
                },
                expected_status=201,
            )
            owned_income_id = int(client.request("GET", "/api/incomes", query={"search": "Income Ownership"})["items"][0]["id"])

            client.request(
                "POST",
                "/api/expenses",
                payload={
                    "expense_date": "2026-04-07",
                    "amount": 44.0,
                    "name": "Expense Ownership",
                    "category": "Altro",
                    "description": "Expense ownership check",
                    "paid_by": "mattia_api",
                    "expense_type": "Personale",
                    "split_type": "equal",
                    "split_ratio": 1.0,
                },
                expected_status=201,
            )
            owned_expense_id = int(client.request("GET", "/api/expenses", query={"search": "Expense Ownership"})["items"][0]["id"])

            calendar_all = client.request("GET", "/api/calendar", query={"month_label": "2026-04", "content_filter": "all"})
            assert calendar_all["month"]["label"] == "2026-04"
            assert calendar_all["month"]["prev_month_label"] == "2026-03"
            assert calendar_all["month"]["next_month_label"] == "2026-05"
            assert calendar_all["summary"]["event_count"] >= 2
            calendar_days = [day for week in calendar_all["weeks"] for day in week["days"]]
            calendar_day = next(day for day in calendar_days if day["date"] == "2026-04-07")
            assert calendar_day["event_count"] >= 2
            assert calendar_day["total_expenses"] >= 44.0
            assert calendar_day["total_incomes"] >= 111.0
            assert any(day["date"] == "2026-03-30" and not day["is_current_month"] for day in calendar_days)

            calendar_incomes = client.request("GET", "/api/calendar", query={"month_label": "2026-04", "content_filter": "incomes"})
            assert calendar_incomes["summary"]["income_count"] >= 1
            assert calendar_incomes["summary"]["expense_count"] == 0

            calendar_expenses = client.request("GET", "/api/calendar", query={"year": 2026, "month": 4, "content_filter": "expenses", "preview_limit": 1})
            assert calendar_expenses["summary"]["expense_count"] >= 1
            assert calendar_expenses["summary"]["income_count"] == 0

            day_detail = client.request("GET", "/api/calendar/day/2026-04-07")
            assert day_detail["day"]["event_count"] >= 2
            assert day_detail["day"]["remaining_count"] == 0

            dashboard = client.request("GET", "/api/dashboard")
            assert "metrics" in dashboard

            meta = client.request("GET", "/api/meta/options")
            assert "categories" in meta and "usernames" in meta

            categories = client.request("GET", "/api/categories")
            initial_category_count = len(categories["items"])
            client.request("POST", "/api/categories", payload={"name": "API Test"})
            categories_after_create = client.request("GET", "/api/categories")
            assert len(categories_after_create["items"]) == initial_category_count + 1
            client.request("DELETE", "/api/categories/API Test")

            expenses_before = client.request("GET", "/api/expenses")
            initial_expense_count = expenses_before["count"]
            client.request(
                "POST",
                "/api/expenses",
                payload={
                    "expense_date": "2026-04-08",
                    "amount": 88.5,
                    "name": "Spesa API",
                    "category": "Casa",
                    "description": "Creata via API",
                    "paid_by": "mattia_api",
                    "expense_type": "Condivisa",
                    "split_type": "custom",
                    "split_ratio": 0.6,
                },
                expected_status=201,
            )
            expenses_after_create = client.request("GET", "/api/expenses", query={"search": "Spesa API"})
            assert expenses_after_create["count"] == 1
            assert "summary" in expenses_after_create and expenses_after_create["summary"]["total_amount"] >= 88.5
            sorted_expenses = client.request("GET", "/api/expenses", query={"month_label": "2026-04", "sort": "amount_desc"})
            assert "sort_options" in sorted_expenses["filters"]
            expense_id = int(expenses_after_create["items"][0]["id"])
            assert client.request("GET", f"/api/expenses/{expense_id}")["item"]["name"] == "Spesa API"
            balance_open = client.request(
                "GET",
                "/api/couple-balance",
                query={"month_label": "2026-04", "status_filter": "open", "category": "Casa"},
            )
            assert balance_open["period"]["label"] == "2026-04"
            assert balance_open["period"]["prev_month_label"] == "2026-03"
            assert balance_open["period"]["next_month_label"] == "2026-05"
            assert balance_open["summary"]["total_unsettled"] >= 88.5
            assert balance_open["summary"]["filtered_items"] >= 1
            assert balance_open["items"][0]["is_shared"] is True
            assert balance_open["items"][0]["status_label"] == "Da regolare"

            client.request("POST", "/api/auth/logout")
            client.request("POST", "/api/auth/login", payload={"username": "compagna", "password": "demo123"})
            client.request("GET", f"/api/incomes/{owned_income_id}", expected_status=404)
            client.request(
                "PUT",
                f"/api/incomes/{owned_income_id}",
                payload={
                    "income_date": "2026-04-08",
                    "amount": 150.0,
                    "source": "Blocked income update",
                    "description": "blocked",
                },
                expected_status=403,
            )
            client.request("DELETE", f"/api/incomes/{owned_income_id}", expected_status=403)
            client.request("GET", f"/api/expenses/{owned_expense_id}", expected_status=404)
            client.request(
                "PUT",
                f"/api/expenses/{owned_expense_id}",
                payload={
                    "expense_date": "2026-04-08",
                    "amount": 50.0,
                    "name": "Blocked expense update",
                    "category": "Altro",
                    "description": "blocked",
                    "paid_by": "compagna",
                    "expense_type": "Personale",
                    "split_type": "equal",
                    "split_ratio": 1.0,
                },
                expected_status=403,
            )
            client.request("DELETE", f"/api/expenses/{owned_expense_id}", expected_status=403)
            assert client.request("GET", f"/api/expenses/{expense_id}")["item"]["name"] == "Spesa API"
            client.request(
                "PATCH",
                f"/api/couple-balance/{expense_id}/settled",
                payload={"is_settled": True},
            )
            balance_settled = client.request(
                "GET",
                "/api/couple-balance",
                query={"month_label": "2026-04", "status_filter": "settled", "category": "Casa"},
            )
            assert any(int(item["id"]) == expense_id and item["settled"] is True for item in balance_settled["items"])

            client.request("POST", "/api/auth/logout")
            client.request("POST", "/api/auth/login", payload={"username": "mattia_api", "password": "secret123"})
            client.request(
                "PUT",
                f"/api/expenses/{expense_id}",
                payload={
                    "expense_date": "2026-04-09",
                    "amount": 99.9,
                    "name": "Spesa API aggiornata",
                    "category": "Casa",
                    "description": "Aggiornata via API",
                    "paid_by": "compagna",
                    "expense_type": "Condivisa",
                    "split_type": "equal",
                    "split_ratio": 0.5,
                },
            )
            updated_expense = client.request("GET", f"/api/expenses/{expense_id}")
            assert updated_expense["item"]["name"] == "Spesa API aggiornata"
            couple_balance = client.request("GET", "/api/couple-balance")
            assert "summary" in couple_balance
            client.request(
                "POST",
                "/api/expenses",
                payload={
                    "expense_date": "2026-04-12",
                    "amount": 12.0,
                    "name": "Bulk API",
                    "category": "Altro",
                    "description": "Bulk delete check",
                    "paid_by": "mattia_api",
                    "expense_type": "Personale",
                    "split_type": "equal",
                    "split_ratio": 1.0,
                },
                expected_status=201,
            )
            bulk_expense = client.request("GET", "/api/expenses", query={"search": "Bulk API"})
            bulk_expense_id = int(bulk_expense["items"][0]["id"])
            bulk_delete = client.request("POST", "/api/expenses/bulk-delete", payload={"ids": [bulk_expense_id]})
            assert bulk_delete["deleted_count"] == 1
            client.request("DELETE", f"/api/expenses/{expense_id}")
            expenses_after_delete = client.request("GET", "/api/expenses")
            assert expenses_after_delete["count"] == initial_expense_count

            incomes_before = client.request("GET", "/api/incomes")
            initial_income_count = incomes_before["count"]
            client.request(
                "POST",
                "/api/incomes",
                payload={
                    "income_date": "2026-04-10",
                    "amount": 321.0,
                    "source": "Test API",
                    "description": "Entrata creata via API",
                },
                expected_status=201,
            )
            incomes_after_create = client.request("GET", "/api/incomes", query={"search": "Test API"})
            assert incomes_after_create["count"] == 1
            assert "summary" in incomes_after_create and incomes_after_create["summary"]["total_amount"] >= 321.0
            sorted_incomes = client.request("GET", "/api/incomes", query={"month_label": "2026-04", "sort": "amount_desc"})
            assert "sort_options" in sorted_incomes["filters"]
            income_id = int(incomes_after_create["items"][0]["id"])
            assert client.request("GET", f"/api/incomes/{income_id}")["item"]["source"] == "Test API"
            client.request(
                "PUT",
                f"/api/incomes/{income_id}",
                payload={
                    "income_date": "2026-04-11",
                    "amount": 654.0,
                    "source": "Test API Aggiornato",
                    "description": "Entrata aggiornata via API",
                },
            )
            updated_income = client.request("GET", f"/api/incomes/{income_id}")
            assert updated_income["item"]["source"] == "Test API Aggiornato"
            client.request("DELETE", f"/api/incomes/{income_id}")
            incomes_after_delete = client.request("GET", "/api/incomes")
            assert incomes_after_delete["count"] == initial_income_count
            client.request("DELETE", f"/api/incomes/{owned_income_id}")
            client.request("DELETE", f"/api/expenses/{owned_expense_id}")

            client.request("POST", "/api/auth/logout")
            client.request("GET", "/api/auth/me", expected_status=401)

            print("OK")
        finally:
            process.terminate()
            process.join(timeout=5)


if __name__ == "__main__":
    run_checks()
