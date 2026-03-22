import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
DB_PATH = os.getenv("DB_PATH", "barkbot.db")
ALLOWED_GROUPS = [int(x.strip()) for x in os.getenv("ALLOWED_GROUPS", "").split(",") if x.strip()]
