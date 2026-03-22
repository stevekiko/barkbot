"""
配置模块 — 从 .env 文件加载环境变量
"""

import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Bot Token（通过 @BotFather 获取）
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# 管理员 Telegram User ID 列表（多个用逗号分隔）
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# SQLite 数据库文件路径
DB_PATH = os.getenv("DB_PATH", "barkbot.db")

# 允许使用 Bot 的群组 ID 列表（留空则不限制，多个用逗号分隔）
ALLOWED_GROUPS = [int(x.strip()) for x in os.getenv("ALLOWED_GROUPS", "").split(",") if x.strip()]
