"""
app/database.py
---------------
SQLite database initialization and connection management.

Connection strategy:
  - :memory: (tests): single shared connection, never closed.
  - File-backed: new connection per call, closed after use.

Usage in models:
    from app.database import db

    with db() as conn:
        row = conn.execute("SELECT ...").fetchone()
"""

import sqlite3
import os
from contextlib import contextmanager

DB_PATH = os.environ.get("DB_PATH", "finance.db")

_shared_conn = None   # used only for :memory:


def _make_conn(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
    return conn


@contextmanager
def db():
    """
    Context manager that yields a SQLite connection.
    Commits on success, rolls back on exception.
    Closes file-backed connections; keeps the :memory: singleton alive.
    """
    global _shared_conn

    if DB_PATH == ":memory:":
        if _shared_conn is None:
            _shared_conn = _make_conn(":memory:")
        conn = _shared_conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        # Don't close — it's the shared singleton
    else:
        conn = _make_conn(DB_PATH)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def init_db():
    """Create all tables if they don't exist. Safe to call on every startup."""
    with db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                email      TEXT NOT NULL UNIQUE,
                password   TEXT NOT NULL,
                role       TEXT NOT NULL CHECK(role IN ('viewer','analyst','admin')),
                status     TEXT NOT NULL DEFAULT 'active'
                               CHECK(status IN ('active','inactive')),
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS records (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL REFERENCES users(id),
                amount     REAL NOT NULL CHECK(amount > 0),
                type       TEXT NOT NULL CHECK(type IN ('income','expense')),
                category   TEXT NOT NULL,
                date       TEXT NOT NULL,
                notes      TEXT,
                deleted_at TEXT,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_records_user     ON records(user_id);
            CREATE INDEX IF NOT EXISTS idx_records_type     ON records(type);
            CREATE INDEX IF NOT EXISTS idx_records_category ON records(category);
            CREATE INDEX IF NOT EXISTS idx_records_date     ON records(date);
            CREATE INDEX IF NOT EXISTS idx_records_deleted  ON records(deleted_at);
        """)
