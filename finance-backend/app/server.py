"""
app/server.py
-------------
Custom HTTP server built on top of Python's http.server.
Handles:
  - JSON request parsing
  - URL routing with path parameters  (/api/users/:id)
  - Query string parsing
  - Rate limiting per IP
  - Consistent JSON response envelope
  - CORS headers for local frontend dev
"""

import json
import re
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from app.database import init_db
from app.middleware.rate_limit import check_rate_limit
from app.utils.helpers import error as err_response

# ─────────────────────────────────────────────────────────────
# Route registry
# ─────────────────────────────────────────────────────────────

_routes = []   # list of (method, pattern_regex, param_names, handler)


def route(method: str, path: str):
    """
    Decorator to register a route.
    Path can contain :param segments, e.g. /api/users/:id
    """
    # Convert :param to named regex groups
    param_names = re.findall(r":(\w+)", path)
    pattern     = re.sub(r":(\w+)", r"([^/]+)", path)
    regex       = re.compile(f"^{pattern}$")

    def decorator(fn):
        _routes.append((method.upper(), regex, param_names, fn))
        return fn
    return decorator


def _match_route(method: str, path: str):
    """Return (handler, kwargs) or (None, None)."""
    for r_method, r_regex, r_params, r_handler in _routes:
        if r_method != method:
            continue
        m = r_regex.match(path)
        if m:
            kwargs = dict(zip(r_params, m.groups()))
            return r_handler, kwargs
    return None, None


# ─────────────────────────────────────────────────────────────
# Request wrapper  (gives routes a nicer API)
# ─────────────────────────────────────────────────────────────

class Request:
    def __init__(self, method, path, headers, query_params, body_bytes):
        self.method       = method
        self.path         = path
        self.headers      = headers
        self.query_params = query_params
        self._body        = body_bytes
        self.current_user = None   # set by auth middleware

    @property
    def json(self):
        try:
            return json.loads(self._body.decode("utf-8")) if self._body else {}
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None


# ─────────────────────────────────────────────────────────────
# HTTP Handler
# ─────────────────────────────────────────────────────────────

class FinanceHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        # Custom compact logging
        print(f"  {self.address_string()} {fmt % args}")

    def _send_json(self, status: int, body: dict, extra_headers: dict = None):
        payload = json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(payload))
        # CORS for local development
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if extra_headers:
            for k, v in extra_headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def _handle(self, method: str):
        parsed      = urlparse(self.path)
        path        = parsed.path.rstrip("/") or "/"
        raw_params  = parse_qs(parsed.query, keep_blank_values=False)
        # Flatten single-value lists:  {"key": ["val"]} → {"key": "val"}
        query_params = {k: v[0] if len(v) == 1 else v for k, v in raw_params.items()}

        # ── Rate limit ─────────────────────────────────────
        ip = self.client_address[0]
        allowed, rl_headers = check_rate_limit(ip)
        if not allowed:
            status, body = err_response("Too many requests — please slow down", 429)
            self._send_json(status, body, rl_headers)
            return

        # ── Read body ──────────────────────────────────────
        length     = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(length) if length > 0 else b""

        # ── Build request object ───────────────────────────
        req = Request(
            method       = method,
            path         = path,
            headers      = dict(self.headers),
            query_params = query_params,
            body_bytes   = body_bytes,
        )

        # ── Route dispatch ─────────────────────────────────
        handler, kwargs = _match_route(method, path)

        if handler is None:
            status, body = err_response(f"Route {method} {path} not found", 404)
            self._send_json(status, body, rl_headers)
            return

        try:
            status, body = handler(req, **kwargs)
        except Exception as exc:
            traceback.print_exc()
            status, body = err_response("Internal server error", 500)

        self._send_json(status, body, rl_headers)

    def do_GET(self):    self._handle("GET")
    def do_POST(self):   self._handle("POST")
    def do_PUT(self):    self._handle("PUT")
    def do_PATCH(self):  self._handle("PATCH")
    def do_DELETE(self): self._handle("DELETE")

    def do_OPTIONS(self):
        # Pre-flight CORS
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()


# ─────────────────────────────────────────────────────────────
# Register all routes
# ─────────────────────────────────────────────────────────────

def register_routes():
    from app.routes import auth, users, records, dashboard

    # Auth
    route("POST", "/api/auth/register")(auth.register)
    route("POST", "/api/auth/login")(auth.login)
    route("GET",  "/api/auth/me")(auth.me)

    # Users  (admin only)
    route("GET",    "/api/users")(users.list_users)
    route("GET",    "/api/users/:user_id")(users.get_user)
    route("PUT",    "/api/users/:user_id")(users.update_user)
    route("DELETE", "/api/users/:user_id")(users.delete_user)
    route("PATCH",  "/api/users/:user_id/status")(users.toggle_status)

    # Financial Records
    route("GET",    "/api/records")(records.list_records)
    route("POST",   "/api/records")(records.create_record)
    route("GET",    "/api/records/:record_id")(records.get_record)
    route("PUT",    "/api/records/:record_id")(records.update_record)
    route("DELETE", "/api/records/:record_id")(records.delete_record)

    # Dashboard
    route("GET", "/api/dashboard/summary")(dashboard.summary)
    route("GET", "/api/dashboard/categories")(dashboard.categories)
    route("GET", "/api/dashboard/trends/monthly")(dashboard.monthly_trends)
    route("GET", "/api/dashboard/trends/weekly")(dashboard.weekly_trends)
    route("GET", "/api/dashboard/activity")(dashboard.recent_activity)

    # Health check
    @route("GET", "/health")
    def health(request):
        from app.utils.helpers import ok
        return ok({"status": "ok", "service": "finance-backend"})


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

def create_app(host="0.0.0.0", port=8000):
    init_db()
    register_routes()
    server = HTTPServer((host, port), FinanceHandler)
    return server


if __name__ == "__main__":
    import os
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))

    print(f"\n{'='*50}")
    print(f"  Finance Backend API")
    print(f"  Running on http://{host}:{port}")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*50}\n")

    server = create_app(host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
