"""
app/utils/helpers.py
---------------------
Shared response builders, validation helpers, and pagination logic.
"""

import json
import re
import uuid
from datetime import datetime, date, timezone


# ─────────────────────────────────────────────────────────────
# JSON response builders
# ─────────────────────────────────────────────────────────────

def ok(data, status=200):
    """Success envelope."""
    return status, {"success": True, "data": data}


def created(data):
    return ok(data, 201)


def error(message, status=400, details=None):
    """Error envelope."""
    body = {"success": False, "error": message}
    if details:
        body["details"] = details
    return status, body


def not_found(resource="Resource"):
    return error(f"{resource} not found", 404)


def forbidden(message="You do not have permission to perform this action"):
    return error(message, 403)


def unauthorized(message="Authentication required"):
    return error(message, 401)


# ─────────────────────────────────────────────────────────────
# Validation helpers
# ─────────────────────────────────────────────────────────────

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def validate_date(date_str: str) -> bool:
    """Check YYYY-MM-DD format."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False


def validate_amount(amount) -> bool:
    try:
        return float(amount) > 0
    except (TypeError, ValueError):
        return False


def new_id() -> str:
    return str(uuid.uuid4())


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─────────────────────────────────────────────────────────────
# Pagination helper
# ─────────────────────────────────────────────────────────────

def parse_pagination(params: dict):
    try:
        page = max(1, int(params.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        limit = min(100, max(1, int(params.get("limit", 20))))
    except (ValueError, TypeError):
        limit = 20
    return page, limit, (page - 1) * limit


def paginate_response(items, total, page, limit):
    return {
        "items":       items,
        "total":       total,
        "page":        page,
        "limit":       limit,
        "total_pages": max(1, -(-total // limit)),   # ceil division
    }


# ─────────────────────────────────────────────────────────────
# Row → dict conversion (sqlite3.Row to plain dict)
# ─────────────────────────────────────────────────────────────

def row_to_dict(row) -> dict:
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows) -> list:
    return [dict(r) for r in rows]
