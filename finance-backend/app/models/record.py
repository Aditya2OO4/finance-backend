"""
app/models/record.py
--------------------
All database operations for financial records.
Soft-delete: deleted_at IS NULL means active.
"""

from app.database import db
from app.utils.helpers import row_to_dict, rows_to_list, new_id, now_iso


VALID_TYPES = {"income", "expense"}


def find_by_id(record_id: str) -> dict | None:
    with db() as conn:
        row = conn.execute(
            "SELECT * FROM records WHERE id = ? AND deleted_at IS NULL",
            (record_id,),
        ).fetchone()
    return row_to_dict(row)


def get_all(filters: dict, page: int, limit: int, offset: int) -> tuple[list, int]:
    where  = ["deleted_at IS NULL"]
    params = []

    if filters.get("type"):
        where.append("type = ?")
        params.append(filters["type"])
    if filters.get("category"):
        where.append("LOWER(category) = LOWER(?)")
        params.append(filters["category"])
    if filters.get("date_from"):
        where.append("date >= ?")
        params.append(filters["date_from"])
    if filters.get("date_to"):
        where.append("date <= ?")
        params.append(filters["date_to"])
    if filters.get("user_id"):
        where.append("user_id = ?")
        params.append(filters["user_id"])

    where_sql = " AND ".join(where)

    with db() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM records WHERE {where_sql}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"SELECT * FROM records WHERE {where_sql} "
            f"ORDER BY date DESC, created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

    return rows_to_list(rows), total


def create(user_id: str, amount: float, type_: str,
           category: str, date: str, notes: str = None) -> dict:
    rid = new_id()
    ts  = now_iso()
    with db() as conn:
        conn.execute(
            "INSERT INTO records "
            "(id, user_id, amount, type, category, date, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (rid, user_id, amount, type_, category, date, notes, ts, ts),
        )
    return find_by_id(rid)


def update(record_id: str, fields: dict) -> dict | None:
    allowed = {"amount", "type", "category", "date", "notes"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return find_by_id(record_id)
    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values     = list(updates.values()) + [record_id]
    with db() as conn:
        conn.execute(
            f"UPDATE records SET {set_clause} WHERE id = ? AND deleted_at IS NULL",
            values,
        )
    return find_by_id(record_id)


def soft_delete(record_id: str) -> bool:
    with db() as conn:
        cursor = conn.execute(
            "UPDATE records SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
            (now_iso(), record_id),
        )
    return cursor.rowcount > 0
