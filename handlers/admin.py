import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)

from config import ADMIN_IDS
from database import add_member, remove_member, get_all_members, get_member, update_member
from bark import push, LEVEL_LABELS
from handlers.start import main_menu_keyboard, MAIN_MENU_TEXT

logger = logging.getLogger(__name__)

# Conversation states
INPUT_USERNAME, INPUT_DISPLAY_NAME, INPUT_BARK_KEY = range(3)
EDIT_VALUE = 10


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _esc(text: str) -> str:
    """Escape MarkdownV2 special characters."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in text)


# ──────────────── Member List ────────────────

def member_list_markup():
    members = get_all_members()
    if not members:
        return None, "📋 *成员列表*\n\n_暂无成员，请先添加_"

    lines = ["📋 *成员列表*\n"]
    buttons = []
    for i, m in enumerate(members, 1):
        dn = _esc(m["display_name"])
        un = _esc(m["telegram_username"])
        lines.append(f"`{i}`\\. {dn}  \\(@{un}\\)")
        buttons.append([
            InlineKeyboardButton(f"✏️ {m['display_name']}", callback_data=f"edit:{m['telegram_username']}"),
            InlineKeyboardButton("🔔", callback_data=f"test:{m['telegram_username']}"),
            InlineKeyboardButton("🗑", callback_data=f"del:{m['telegram_username']}"),
        ])
    buttons.append([InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")])
    return InlineKeyboardMarkup(buttons), "\n".join(lines)


async def show_member_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    # Clear any lingering conversation state
    context.user_data.pop("edit_username", None)
    context.user_data.pop("edit_field", None)
    context.user_data.pop("new_username", None)
    context.user_data.pop("new_display_name", None)

    markup, text = member_list_markup()
    try:
        if markup:
            await query.edit_message_text(text, reply_markup=markup, parse_mode="MarkdownV2")
        else:
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ 添加成员", callback_data="menu:add")],
                    [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")],
                ]),
                parse_mode="MarkdownV2",
            )
    except Exception as e:
        logger.error(f"show_member_list MarkdownV2 error: {e}")
        # Fallback: send without markdown
        plain = text.replace("*", "").replace("\\", "").replace("`", "").replace("_", "")
        await query.edit_message_text(
            plain,
            reply_markup=markup or InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")]
            ]),
        )


# ──────────────── Add Member (Conversation) ────────────────

async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END
    await query.edit_message_text(
        "➕ 添加成员\n\n请输入 Telegram 用户名（不含 @）：",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ 取消", callback_data="conv:cancel")]
        ]),
    )
    return INPUT_USERNAME


async def input_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.message.text.strip().lstrip("@").lower()
    if not username:
        await update.message.reply_text("⚠️ 用户名不能为空，请重新输入：")
        return INPUT_USERNAME
    if get_member(username):
        await update.message.reply_text(f"⚠️ @{username} 已存在，请输入其他用户名：")
        return INPUT_USERNAME
    context.user_data["new_username"] = username
    await update.message.reply_text(
        f"👤 用户名: @{username}\n\n请输入显示名称：",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ 取消", callback_data="conv:cancel")]
        ]),
    )
    return INPUT_DISPLAY_NAME


async def input_display_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    display_name = update.message.text.strip()
    if not display_name:
        await update.message.reply_text("⚠️ 显示名称不能为空，请重新输入：")
        return INPUT_DISPLAY_NAME
    context.user_data["new_display_name"] = display_name
    await update.message.reply_text(
        f"📝 显示名称: {display_name}\n\n请输入 Bark Key：",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ 取消", callback_data="conv:cancel")]
        ]),
    )
    return INPUT_BARK_KEY


async def input_bark_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bark_key = update.message.text.strip()
    if not bark_key:
        await update.message.reply_text("⚠️ Bark Key 不能为空，请重新输入：")
        return INPUT_BARK_KEY

    username = context.user_data.pop("new_username", "")
    display_name = context.user_data.pop("new_display_name", "")

    if add_member(username, display_name, bark_key):
        await update.message.reply_text(
            f"✅ 成员添加成功\n\n"
            f"👤 {display_name}\n"
            f"🔗 @{username}\n"
            f"🔑 Bark Key 已保存",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 查看成员列表", callback_data="menu:list")],
                [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")],
            ]),
        )
    else:
        await update.message.reply_text(
            f"⚠️ 添加失败，@{username} 可能已存在",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")]
            ]),
        )
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("new_username", None)
    context.user_data.pop("new_display_name", None)
    context.user_data.pop("edit_username", None)
    context.user_data.pop("edit_field", None)
    await query.edit_message_text(
        "🔔 BarkBot 管理面板\n\n选择操作：",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


# ──────────────── Edit Member ────────────────

async def edit_member_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return ConversationHandler.END

    username = query.data.split(":")[1]
    member = get_member(username)
    if not member:
        await query.edit_message_text("⚠️ 该成员已被删除")
        return ConversationHandler.END

    context.user_data["edit_username"] = username
    masked_key = member["bark_key"][:6] + "..." if len(member["bark_key"]) > 6 else "***"
    await query.edit_message_text(
        f"✏️ 修改成员信息\n\n"
        f"👤 {member['display_name']}\n"
        f"🔗 @{username}\n"
        f"🔑 {masked_key}\n\n"
        f"选择要修改的字段：",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📝 修改名称", callback_data="editfield:display_name"),
                InlineKeyboardButton("🔑 修改 Bark Key", callback_data="editfield:bark_key"),
            ],
            [InlineKeyboardButton("⬅️ 返回列表", callback_data="menu:list")],
        ]),
    )
    return EDIT_VALUE


async def edit_select_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    field = query.data.split(":")[1]
    context.user_data["edit_field"] = field
    label = "显示名称" if field == "display_name" else "Bark Key"
    emoji = "📝" if field == "display_name" else "🔑"
    await query.edit_message_text(
        f"{emoji} 请输入新的{label}：",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ 取消", callback_data="conv:cancel")]
        ]),
    )
    return EDIT_VALUE


async def edit_input_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = update.message.text.strip()
    username = context.user_data.pop("edit_username", "")
    field = context.user_data.pop("edit_field", "")

    if not value or not username or not field:
        await update.message.reply_text("⚠️ 操作失败，请重试")
        return ConversationHandler.END

    label = "显示名称" if field == "display_name" else "Bark Key"

    if update_member(username, field, value):
        await update.message.reply_text(
            f"✅ 已更新 @{username} 的{label}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 返回列表", callback_data="menu:list"),
                 InlineKeyboardButton("⬅️ 主菜单", callback_data="menu:back")]
            ]),
        )
    else:
        await update.message.reply_text("⚠️ 更新失败")
    return ConversationHandler.END


# ──────────────── Delete Member ────────────────

async def delete_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    username = query.data.split(":")[1]
    member = get_member(username)
    if not member:
        await query.edit_message_text("⚠️ 该成员已被删除")
        return

    await query.edit_message_text(
        f"🗑 确认删除\n\n"
        f"确定要删除 {member['display_name']}（@{username}）吗？\n"
        f"此操作不可恢复！",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ 确定删除", callback_data=f"delyes:{username}"),
                InlineKeyboardButton("❌ 取消", callback_data="menu:list"),
            ]
        ]),
    )


async def delete_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer()
        return

    username = query.data.split(":")[1]
    if remove_member(username):
        await query.answer("✅ 已删除", show_alert=True)
    else:
        await query.answer("⚠️ 删除失败", show_alert=True)

    markup, text = member_list_markup()
    try:
        if markup:
            await query.edit_message_text(text, reply_markup=markup, parse_mode="MarkdownV2")
        else:
            await query.edit_message_text(
                "📋 成员列表\n\n暂无成员",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ 添加成员", callback_data="menu:add")],
                    [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")],
                ]),
            )
    except Exception as e:
        logger.error(f"delete_execute display error: {e}")
        await query.edit_message_text(
            "📋 成员列表（已更新）",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 刷新列表", callback_data="menu:list")],
                [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")],
            ]),
        )


# ──────────────── Test Push ────────────────

async def test_select_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    members = get_all_members()
    if not members:
        await query.edit_message_text(
            "暂无成员，请先添加",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ 添加成员", callback_data="menu:add")],
                [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")],
            ]),
        )
        return

    buttons = []
    for m in members:
        buttons.append([InlineKeyboardButton(
            f"🔔 {m['display_name']}（@{m['telegram_username']}）",
            callback_data=f"test:{m['telegram_username']}",
        )])
    buttons.append([InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")])
    await query.edit_message_text(
        "🔔 测试推送\n\n选择要推送的成员：",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def test_select_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    username = query.data.split(":")[1]
    member = get_member(username)
    if not member:
        await query.edit_message_text("⚠️ 该成员已被删除")
        return

    await query.edit_message_text(
        f"🔔 测试推送\n\n"
        f"目标: {member['display_name']}\n\n"
        f"选择通知级别：\n\n"
        f"📢 普通 — 正常通知提醒\n"
        f"⚡ 优先 — 突破专注模式\n"
        f"🚨 紧急 — 绕过静音，持续响铃",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 普通", callback_data=f"testpush:{username}:1")],
            [InlineKeyboardButton("⚡ 优先", callback_data=f"testpush:{username}:2")],
            [InlineKeyboardButton("🚨 紧急（绕过静音）", callback_data=f"testpush:{username}:3")],
            [InlineKeyboardButton("⬅️ 返回主菜单", callback_data="menu:back")],
        ]),
    )


async def test_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        return

    parts = query.data.split(":")
    username, level = parts[1], int(parts[2])
    member = get_member(username)
    if not member:
        await query.edit_message_text("⚠️ 该成员已被删除")
        return

    success = await push(member["bark_server"], member["bark_key"], level)
    label = LEVEL_LABELS[level]

    if success:
        text = f"✅ 推送成功\n\n目标: {member['display_name']}\n级别: {label}"
    else:
        text = f"❌ 推送失败\n\n目标: {member['display_name']}\n请检查 Bark Key 是否正确"

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔔 继续测试", callback_data="menu:test")],
            [InlineKeyboardButton("📋 成员列表", callback_data="menu:list"),
             InlineKeyboardButton("⬅️ 主菜单", callback_data="menu:back")],
        ]),
    )
