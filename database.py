from __future__ import annotations

import logging
import sqlite3
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_username TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            bark_key TEXT NOT NULL,
            bark_server TEXT DEFAULT 'https://api.day.app',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS push_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_username TEXT NOT NULL,
            level INTEGER NOT NULL,
            sender_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


def add_member(username: str, display_name: str, bark_key: str, bark_server: str = "https://api.day.app") -> bool:
    try:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO members (telegram_username, display_name, bark_key, bark_server) VALUES (?, ?, ?, ?)",
                (username.lower(), display_name, bark_key, bark_server),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"add_member 异常: {e}")
        return False


def remove_member(username: str) -> bool:
    try:
        conn = get_conn()
        cursor = conn.execute("DELETE FROM members WHERE telegram_username = ?", (username.lower(),))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()
        return deleted
    except Exception as e:
        logger.error(f"remove_member 异常: {e}")
        return False


def get_member(username: str) -> dict | None:
    try:
        conn = get_conn()
        row = conn.execute("SELECT * FROM members WHERE telegram_username = ?", (username.lower(),)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_member 异常: {e}")
        return None


def get_all_members() -> list[dict]:
    try:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM members ORDER BY created_at").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_all_members 异常: {e}")
        return []


def update_member(username: str, field: str, value: str) -> bool:
    if field not in ("display_name", "bark_key"):
        return False
    try:
        conn = get_conn()
        cursor = conn.execute(
            f"UPDATE members SET {field} = ? WHERE telegram_username = ?",
            (value, username.lower()),
        )
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated
    except Exception as e:
        logger.error(f"update_member 异常: {e}")
        return False


def log_push(target_username: str, level: int, sender_id: int):
    try:
        conn = get_conn()
        conn.execute(
            "INSERT INTO push_log (target_username, level, sender_id) VALUES (?, ?, ?)",
            (target_username, level, sender_id),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"log_push 异常: {e}")
