"""
数据库模块 — SQLite 存储成员信息和推送日志

表结构：
  - members:  成员信息（用户名、显示名、Bark Key 等）
  - push_log: 推送记录（目标、级别、发送人、时间）
"""

from __future__ import annotations

import logging
import sqlite3
from config import DB_PATH

logger = logging.getLogger(__name__)


def get_conn() -> sqlite3.Connection:
    """获取数据库连接，使用 WAL 模式提升并发性能"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row   # 查询结果可通过列名访问
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化数据库，创建必要的表（如果不存在）"""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_username TEXT UNIQUE NOT NULL,  -- Telegram 用户名（小写）
            display_name TEXT NOT NULL,              -- 显示名称
            bark_key TEXT NOT NULL,                  -- Bark 推送 Key
            bark_server TEXT DEFAULT 'https://api.day.app',  -- Bark 服务器地址
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS push_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_username TEXT NOT NULL,   -- 推送目标用户名
            level INTEGER NOT NULL,          -- 通知级别（1/2/3）
            sender_id INTEGER,               -- 发送人 Telegram ID
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()
    conn.close()


def add_member(username: str, display_name: str, bark_key: str, bark_server: str = "https://api.day.app") -> bool:
    """
    添加成员

    返回: True 添加成功，False 用户名已存在或其他异常
    """
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
            # 用户名已存在（UNIQUE 约束冲突）
            return False
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"add_member 异常: {e}")
        return False


def remove_member(username: str) -> bool:
    """删除成员，返回是否成功删除"""
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
    """根据用户名查询成员信息，不存在返回 None"""
    try:
        conn = get_conn()
        row = conn.execute("SELECT * FROM members WHERE telegram_username = ?", (username.lower(),)).fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_member 异常: {e}")
        return None


def get_all_members() -> list[dict]:
    """获取全部成员列表，按创建时间排序"""
    try:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM members ORDER BY created_at").fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"get_all_members 异常: {e}")
        return []


def update_member(username: str, field: str, value: str) -> bool:
    """
    更新成员信息

    参数:
        field: 允许修改的字段（display_name 或 bark_key）
        value: 新值

    返回: True 更新成功，False 失败
    """
    # 白名单校验，防止 SQL 注入
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
    """记录一次推送操作到日志表"""
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
