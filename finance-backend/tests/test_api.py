"""
tests/test_api.py
-----------------
Integration tests — spin up the real server, hit it with HTTP.
Uses an in-memory SQLite DB so tests are isolated and fast.
"""

import sys
import os

# Must set DB_PATH before any app imports so the singleton picks it up
os.environ["DB_PATH"] = ":memory:"
os.environ["RATE_LIMIT_DISABLE"] = "1"
os.environ["SECRET_KEY"] = "test-secret"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import threading
import time
import urllib.request
import urllib.error
import unittest

BASE_URL = "http://127.0.0.1:8765"

# ─────────────────────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────────────────────

def _req(method, path, body=None, token=None):
    url     = BASE_URL + path
    data    = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def get(path, token=None):             return _req("GET",    path, token=token)
def post(path, body, token=None):      return _req("POST",   path, body, token)
def put(path, body, token=None):       return _req("PUT",    path, body, token)
def delete(path, token=None):          return _req("DELETE", path, token=token)
def patch(path, body=None, token=None):return _req("PATCH",  path, body, token)

# ─────────────────────────────────────────────────────────────
# Server lifecycle
# ─────────────────────────────────────────────────────────────

_server = None

def setUpModule():
    global _server
    from app.server import create_app
    _server = create_app("127.0.0.1", 8765)
    t = threading.Thread(target=_server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.2)   # let server bind

def tearDownModule():
    if _server:
        _server.shutdown()

# ─────────────────────────────────────────────────────────────
# Helper: register + login, returns token and user id
# ─────────────────────────────────────────────────────────────

_counter = 0
def unique_email(prefix="user"):
    global _counter
    _counter += 1
    return f"{prefix}_{_counter}@test.dev"

def register_and_login(role="viewer", prefix=None):
    email = unique_email(prefix or role)
    password = "Password1!"
    post("/api/auth/register", {
        "name": f"Test {role.title()}", "email": email,
        "password": password, "role": role,
    })
    _, body = post("/api/auth/login", {"email": email, "password": password})
    data = body.get("data", {})
    return data.get("token"), data.get("user", {}).get("id")

# ─────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────

class TestHealth(unittest.TestCase):
    def test_health(self):
        status, body = get("/health")
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "ok")


class TestAuth(unittest.TestCase):

    def test_register_success(self):
        status, body = post("/api/auth/register", {
            "name": "Alice", "email": unique_email("alice"),
            "password": "Secret123!", "role": "viewer",
        })
        self.assertEqual(status, 201)
        self.assertIn("token", body["data"])
        self.assertNotIn("password", body["data"]["user"])

    def test_register_duplicate_email(self):
        email = unique_email("dup")
        post("/api/auth/register", {"name": "X", "email": email, "password": "Password1!", "role": "viewer"})
        status, _ = post("/api/auth/register", {"name": "Y", "email": email, "password": "Password1!", "role": "viewer"})
        self.assertEqual(status, 409)

    def test_register_missing_fields(self):
        status, body = post("/api/auth/register", {"email": "bad"})
        self.assertEqual(status, 422)
        self.assertFalse(body["success"])

    def test_register_short_password(self):
        status, _ = post("/api/auth/register", {
            "name": "X", "email": unique_email(), "password": "abc", "role": "viewer"
        })
        self.assertEqual(status, 422)

    def test_register_invalid_role(self):
        status, _ = post("/api/auth/register", {
            "name": "X", "email": unique_email(), "password": "Password1!", "role": "superadmin"
        })
        self.assertEqual(status, 422)

    def test_login_success(self):
        email = unique_email("login")
        post("/api/auth/register", {"name": "L", "email": email, "password": "Password1!", "role": "viewer"})
        status, body = post("/api/auth/login", {"email": email, "password": "Password1!"})
        self.assertEqual(status, 200)
        self.assertIn("token", body["data"])

    def test_login_wrong_password(self):
        email = unique_email("wp")
        post("/api/auth/register", {"name": "W", "email": email, "password": "Password1!", "role": "viewer"})
        status, _ = post("/api/auth/login", {"email": email, "password": "wrongpassword"})
        self.assertEqual(status, 401)

    def test_login_unknown_email(self):
        status, _ = post("/api/auth/login", {"email": "nobody@nowhere.com", "password": "x"})
        self.assertEqual(status, 401)

    def test_me_authenticated(self):
        token, _ = register_and_login("viewer", "me_auth")
        status, body = get("/api/auth/me", token=token)
        self.assertEqual(status, 200)
        self.assertNotIn("password", body["data"])

    def test_me_unauthenticated(self):
        status, _ = get("/api/auth/me")
        self.assertEqual(status, 401)

    def test_me_bad_token(self):
        status, _ = get("/api/auth/me", token="Bearer not.a.real.token")
        self.assertEqual(status, 401)


class TestRecords(unittest.TestCase):

    def setUp(self):
        self.admin_token, self.admin_id = register_and_login("admin", "rec_admin")
        self.viewer_token, _            = register_and_login("viewer", "rec_viewer")

    def _make_record(self, overrides=None):
        payload = {"amount": 1500.0, "type": "income", "category": "Salary",
                   "date": "2024-03-01", "notes": "March salary"}
        if overrides:
            payload.update(overrides)
        return post("/api/records", payload, token=self.admin_token)

    def test_create_record_admin(self):
        status, body = self._make_record()
        self.assertEqual(status, 201)
        self.assertEqual(body["data"]["amount"], 1500.0)
        self.assertEqual(body["data"]["type"], "income")

    def test_create_record_viewer_forbidden(self):
        status, _ = post("/api/records", {
            "amount": 100, "type": "expense", "category": "Food", "date": "2024-01-01"
        }, token=self.viewer_token)
        self.assertEqual(status, 403)

    def test_create_record_unauthenticated(self):
        status, _ = post("/api/records", {"amount": 100, "type": "income", "category": "X", "date": "2024-01-01"})
        self.assertEqual(status, 401)

    def test_create_record_negative_amount(self):
        status, _ = self._make_record({"amount": -50})
        self.assertEqual(status, 422)

    def test_create_record_zero_amount(self):
        status, _ = self._make_record({"amount": 0})
        self.assertEqual(status, 422)

    def test_create_record_bad_type(self):
        status, _ = self._make_record({"type": "transfer"})
        self.assertEqual(status, 422)

    def test_create_record_bad_date(self):
        status, _ = self._make_record({"date": "01-01-2024"})
        self.assertEqual(status, 422)

    def test_create_record_missing_category(self):
        status, _ = self._make_record({"category": ""})
        self.assertEqual(status, 422)

    def test_list_records_viewer(self):
        status, body = get("/api/records", token=self.viewer_token)
        self.assertEqual(status, 200)
        self.assertIn("items", body["data"])
        self.assertIn("total", body["data"])

    def test_list_records_unauthenticated(self):
        status, _ = get("/api/records")
        self.assertEqual(status, 401)

    def test_list_records_pagination(self):
        status, body = get("/api/records?page=1&limit=5", token=self.admin_token)
        self.assertEqual(status, 200)
        self.assertLessEqual(len(body["data"]["items"]), 5)

    def test_list_records_filter_type(self):
        status, body = get("/api/records?type=income", token=self.admin_token)
        self.assertEqual(status, 200)

    def test_list_records_filter_invalid_type(self):
        status, _ = get("/api/records?type=potato", token=self.admin_token)
        self.assertEqual(status, 422)

    def test_list_records_filter_date_range_inverted(self):
        status, _ = get("/api/records?date_from=2024-12-01&date_to=2024-01-01", token=self.admin_token)
        self.assertEqual(status, 422)

    def test_get_record_by_id(self):
        _, created = self._make_record()
        rid = created["data"]["id"]
        status, body = get(f"/api/records/{rid}", token=self.viewer_token)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["id"], rid)

    def test_get_nonexistent_record(self):
        status, _ = get("/api/records/does-not-exist", token=self.admin_token)
        self.assertEqual(status, 404)

    def test_update_record_admin(self):
        _, created = self._make_record()
        rid = created["data"]["id"]
        status, body = put(f"/api/records/{rid}", {"amount": 2000}, token=self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["amount"], 2000)

    def test_update_record_viewer_forbidden(self):
        _, created = self._make_record()
        rid = created["data"]["id"]
        status, _ = put(f"/api/records/{rid}", {"amount": 999}, token=self.viewer_token)
        self.assertEqual(status, 403)

    def test_update_record_invalid_amount(self):
        _, created = self._make_record()
        rid = created["data"]["id"]
        status, _ = put(f"/api/records/{rid}", {"amount": -100}, token=self.admin_token)
        self.assertEqual(status, 422)

    def test_soft_delete_record(self):
        _, created = self._make_record()
        rid = created["data"]["id"]
        status, _ = delete(f"/api/records/{rid}", token=self.admin_token)
        self.assertEqual(status, 200)
        # After soft delete, record should be gone
        status2, _ = get(f"/api/records/{rid}", token=self.admin_token)
        self.assertEqual(status2, 404)

    def test_delete_viewer_forbidden(self):
        _, created = self._make_record()
        rid = created["data"]["id"]
        status, _ = delete(f"/api/records/{rid}", token=self.viewer_token)
        self.assertEqual(status, 403)

    def test_delete_nonexistent(self):
        status, _ = delete("/api/records/ghost-id", token=self.admin_token)
        self.assertEqual(status, 404)


class TestDashboard(unittest.TestCase):

    def setUp(self):
        self.admin_token,   _ = register_and_login("admin",   "dash_admin")
        self.viewer_token,  _ = register_and_login("viewer",  "dash_viewer")
        self.analyst_token, _ = register_and_login("analyst", "dash_analyst")

    def test_summary_admin(self):
        status, body = get("/api/dashboard/summary", token=self.admin_token)
        self.assertEqual(status, 200)
        d = body["data"]
        self.assertIn("total_income",   d)
        self.assertIn("total_expenses", d)
        self.assertIn("net_balance",    d)
        self.assertIn("total_records",  d)

    def test_summary_viewer(self):
        status, body = get("/api/dashboard/summary", token=self.viewer_token)
        self.assertEqual(status, 200)

    def test_summary_analyst(self):
        status, body = get("/api/dashboard/summary", token=self.analyst_token)
        self.assertEqual(status, 200)

    def test_summary_unauthenticated(self):
        status, _ = get("/api/dashboard/summary")
        self.assertEqual(status, 401)

    def test_categories_all_roles(self):
        for token in [self.admin_token, self.viewer_token, self.analyst_token]:
            status, body = get("/api/dashboard/categories", token=token)
            self.assertEqual(status, 200)
            self.assertIsInstance(body["data"], list)

    def test_monthly_trends_viewer_forbidden(self):
        status, _ = get("/api/dashboard/trends/monthly", token=self.viewer_token)
        self.assertEqual(status, 403)

    def test_monthly_trends_analyst_allowed(self):
        status, body = get("/api/dashboard/trends/monthly", token=self.analyst_token)
        self.assertEqual(status, 200)
        self.assertIsInstance(body["data"], list)

    def test_monthly_trends_admin(self):
        status, body = get("/api/dashboard/trends/monthly?months=6", token=self.admin_token)
        self.assertEqual(status, 200)

    def test_weekly_trends_analyst(self):
        status, body = get("/api/dashboard/trends/weekly", token=self.analyst_token)
        self.assertEqual(status, 200)

    def test_weekly_trends_viewer_forbidden(self):
        status, _ = get("/api/dashboard/trends/weekly", token=self.viewer_token)
        self.assertEqual(status, 403)

    def test_recent_activity_all_roles(self):
        for token in [self.admin_token, self.viewer_token, self.analyst_token]:
            status, body = get("/api/dashboard/activity", token=token)
            self.assertEqual(status, 200)
            self.assertIsInstance(body["data"], list)


class TestUserManagement(unittest.TestCase):

    def setUp(self):
        self.admin_token,  self.admin_id  = register_and_login("admin",  "usr_admin")
        self.viewer_token, self.viewer_id = register_and_login("viewer", "usr_viewer")

    def test_list_users_admin(self):
        status, body = get("/api/users", token=self.admin_token)
        self.assertEqual(status, 200)
        self.assertIn("items", body["data"])

    def test_list_users_viewer_forbidden(self):
        status, _ = get("/api/users", token=self.viewer_token)
        self.assertEqual(status, 403)

    def test_get_user_admin(self):
        status, body = get(f"/api/users/{self.viewer_id}", token=self.admin_token)
        self.assertEqual(status, 200)
        self.assertNotIn("password", body["data"])

    def test_get_nonexistent_user(self):
        status, _ = get("/api/users/no-such-id", token=self.admin_token)
        self.assertEqual(status, 404)

    def test_update_user_role(self):
        status, body = put(f"/api/users/{self.viewer_id}", {"role": "analyst"}, token=self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["role"], "analyst")

    def test_update_invalid_role(self):
        status, _ = put(f"/api/users/{self.viewer_id}", {"role": "god"}, token=self.admin_token)
        self.assertEqual(status, 422)

    def test_cannot_modify_self(self):
        status, _ = put(f"/api/users/{self.admin_id}", {"name": "Hacked"}, token=self.admin_token)
        self.assertEqual(status, 400)

    def test_toggle_status_active_to_inactive(self):
        status, body = patch(f"/api/users/{self.viewer_id}/status", token=self.admin_token)
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "inactive")

    def test_toggle_status_back(self):
        patch(f"/api/users/{self.viewer_id}/status", token=self.admin_token)  # → inactive
        status, body = patch(f"/api/users/{self.viewer_id}/status", token=self.admin_token)  # → active
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["status"], "active")

    def test_cannot_toggle_own_status(self):
        status, _ = patch(f"/api/users/{self.admin_id}/status", token=self.admin_token)
        self.assertEqual(status, 400)

    def test_delete_user_admin(self):
        _, uid = register_and_login("viewer", "delete_target")
        status, _ = delete(f"/api/users/{uid}", token=self.admin_token)
        self.assertEqual(status, 200)

    def test_cannot_delete_self(self):
        status, _ = delete(f"/api/users/{self.admin_id}", token=self.admin_token)
        self.assertEqual(status, 400)

    def test_no_password_in_any_response(self):
        status, body = get("/api/users", token=self.admin_token)
        for user in body["data"]["items"]:
            self.assertNotIn("password", user)


if __name__ == "__main__":
    unittest.main(verbosity=2)
