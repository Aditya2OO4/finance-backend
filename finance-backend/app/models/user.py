"""
app/models/user.py
------------------
All database operations related to users.
"""

from app.database import db
from app.utils.helpers import row_to_dict, rows_to_list, new_id, now_iso


VALID_ROLES    = {"viewer", "analyst", "admin"}
VALID_STATUSES = {"active", "inactive"}


def find_by_id(user_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return row_to_dict(row)


def find_by_email(email: str) -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return row_to_dict(row)


def get_all(page: int, limit: int, offset: int) -> tuple[list, int]:
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        rows  = conn.execute(
            "SELECT id, name, email, role, status, created_at, updated_at "
            "FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return rows_to_list(rows), total


def create(name: str, email: str, hashed_password: str, role: str) -> dict:
    uid = new_id()
    ts  = now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO users (id, name, email, password, role, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'active', ?, ?)",
            (uid, name, email, hashed_password, role, ts, ts),
        )
    return find_by_id(uid)


def update(user_id: str, fields: dict) -> dict | None:
    allowed = {"name", "role", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return find_by_id(user_id)
    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values     = list(updates.values()) + [user_id]
    with db() as conn:
        conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    return find_by_id(user_id)


def delete(user_id: str) -> bool:
    with db() as conn:
        cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return cursor.rowcount > 0


def safe_user(user: dict) -> dict:
    """Strip the password hash before sending to client."""
    if user is None:
        return None
    return {k: v for k, v in user.items() if k != "password"}
