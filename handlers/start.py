from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS


def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ 添加成员", callback_data="menu:add"),
            InlineKeyboardButton("📋 成员列表", callback_data="menu:list"),
        ],
        [
            InlineKeyboardButton("🔔 测试推送", callback_data="menu:test"),
            InlineKeyboardButton("ℹ️ 使用帮助", callback_data="menu:help"),
        ],
    ])


MAIN_MENU_TEXT = "🔔 BarkBot 管理面板\n\n选择操作："

HELP_TEXT = (
    "ℹ️ 使用帮助\n\n"
    "【管理面板（私聊 Bot）】\n"
    "➕ 添加成员 — 分步引导添加\n"
    "📋 成员列表 — 查看 / 修改 / 删除\n"
    "🔔 测试推送 — 向成员发送测试通知\n\n"
    "【群组使用】\n"
    "在群组中 @成员 即可触发推送按钮\n"
    "点击按钮选择通知级别即可推送\n\n"
    "【通知级别说明】\n"
    "📢 普通 — 正常通知提醒\n"
    "⚡ 优先 — 突破专注/勿扰模式\n"
    "🚨 紧急 — 绕过静音，最大音量持续响铃\n\n"
    "⚠️ 紧急通知会二次确认，请勿滥用！"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ 仅管理员可使用此 Bot")
        return
    await update.message.reply_text(
        MAIN_MENU_TEXT,
        reply_markup=main_menu_keyboard(),
    )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in ADMIN_IDS:
        return

    action = query.data.split(":")[1] if ":" in query.data else ""

    if action == "help":
        await query.edit_message_text(
            HELP_TEXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")]
            ]),
        )
    elif action == "back":
        await query.edit_message_text(
            MAIN_MENU_TEXT,
            reply_markup=main_menu_keyboard(),
        )
