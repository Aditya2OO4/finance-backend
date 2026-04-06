"""
app/models/dashboard.py
------------------------
Aggregation queries for dashboard summary APIs.
"""

from app.database import db
from app.utils.helpers import rows_to_list


def get_summary(user_id: str = None) -> dict:
    where  = "deleted_at IS NULL"
    params = []
    if user_id:
        where += " AND user_id = ?"
        params.append(user_id)

    with db() as conn:
        row = conn.execute(f"""
            SELECT
                COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 0) AS total_income,
                COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 0) AS total_expenses,
                COALESCE(SUM(CASE WHEN type='income'  THEN  amount
                                  WHEN type='expense' THEN -amount END), 0)        AS net_balance,
                COUNT(*) AS total_records
            FROM records WHERE {where}
        """, params).fetchone()
    return dict(row)


def get_category_breakdown(user_id: str = None) -> list:
    where  = "deleted_at IS NULL"
    params = []
    if user_id:
        where += " AND user_id = ?"
        params.append(user_id)

    with db() as conn:
        rows = conn.execute(f"""
            SELECT category, type,
                   ROUND(SUM(amount), 2) AS total,
                   COUNT(*)              AS count
            FROM records WHERE {where}
            GROUP BY category, type ORDER BY total DESC
        """, params).fetchall()
    return rows_to_list(rows)


def get_monthly_trends(user_id: str = None, months: int = 12) -> list:
    where  = "deleted_at IS NULL"
    params = []
    if user_id:
        where += " AND user_id = ?"
        params.append(user_id)

    with db() as conn:
        rows = conn.execute(f"""
            SELECT
                strftime('%Y-%m', date)                                             AS month,
                ROUND(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 2)     AS income,
                ROUND(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 2)     AS expenses,
                ROUND(SUM(CASE WHEN type='income'  THEN  amount
                               WHEN type='expense' THEN -amount END), 2)            AS net
            FROM records WHERE {where}
            GROUP BY month ORDER BY month DESC LIMIT ?
        """, params + [months]).fetchall()
    return list(reversed(rows_to_list(rows)))


def get_weekly_trends(user_id: str = None, weeks: int = 8) -> list:
    where  = "deleted_at IS NULL"
    params = []
    if user_id:
        where += " AND user_id = ?"
        params.append(user_id)

    with db() as conn:
        rows = conn.execute(f"""
            SELECT
                strftime('%Y-W%W', date)                                            AS week,
                ROUND(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END), 2)     AS income,
                ROUND(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END), 2)     AS expenses,
                ROUND(SUM(CASE WHEN type='income'  THEN  amount
                               WHEN type='expense' THEN -amount END), 2)            AS net
            FROM records WHERE {where}
            GROUP BY week ORDER BY week DESC LIMIT ?
        """, params + [weeks]).fetchall()
    return list(reversed(rows_to_list(rows)))


def get_recent_activity(user_id: str = None, limit: int = 10) -> list:
    where  = "r.deleted_at IS NULL"
    params = []
    if user_id:
        where += " AND r.user_id = ?"
        params.append(user_id)

    with db() as conn:
        rows = conn.execute(f"""
            SELECT r.*, u.name AS user_name
            FROM records r JOIN users u ON u.id = r.user_id
            WHERE {where}
            ORDER BY r.date DESC, r.created_at DESC LIMIT ?
        """, params + [limit]).fetchall()
    return rows_to_list(rows)
