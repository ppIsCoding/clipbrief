import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")
FREE_DAILY_SUMMARY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "3"))


def get_db_path():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return DB_PATH


@contextmanager
def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                daily_summary_count INTEGER DEFAULT 0,
                last_summary_date TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            """
        )


def get_user_by_email(email: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def create_user(email: str, password_hash: str) -> dict:
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, password_hash),
        )
        return {"id": cursor.lastrowid, "email": email}


def check_summary_quota(user_id: int) -> tuple[bool, int]:
    """Return (allowed, remaining) without consuming a quota."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return False, 0
        used = user["daily_summary_count"] if user["last_summary_date"] == today else 0
        if used >= FREE_DAILY_SUMMARY_LIMIT:
            return False, 0
        return True, FREE_DAILY_SUMMARY_LIMIT - used


def increment_summary(user_id: int) -> int:
    """Consume one quota after a successful summary. Returns remaining count."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not user:
            return 0
        if user["last_summary_date"] != today:
            conn.execute(
                "UPDATE users SET daily_summary_count = 1, last_summary_date = ? WHERE id = ?",
                (today, user_id),
            )
            return FREE_DAILY_SUMMARY_LIMIT - 1
        conn.execute(
            "UPDATE users SET daily_summary_count = daily_summary_count + 1 WHERE id = ?",
            (user_id,),
        )
        return max(0, FREE_DAILY_SUMMARY_LIMIT - user["daily_summary_count"] - 1)
