import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bark import push, LEVEL_LABELS
from config import ALLOWED_GROUPS, ADMIN_IDS
from database import get_member, log_push

logger = logging.getLogger(__name__)


async def log_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat:
        logger.info(f"群组消息 - 群组: {chat.title} (ID: {chat.id})")


async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    chat = message.chat

    # Only work in group/supergroup chats
    if chat.type not in ("group", "supergroup"):
        return

    # Check group whitelist
    if ALLOWED_GROUPS and chat.id not in ALLOWED_GROUPS:
        return

    # Extract @mentions
    mentions = set()
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                username = message.text[entity.offset + 1 : entity.offset + entity.length].lower()
                mentions.add(username)

    if not mentions:
        return

    for username in mentions:
        member = get_member(username)
        if member:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📢 普通", callback_data=f"push:{username}:1"),
                    InlineKeyboardButton("⚡ 优先", callback_data=f"push:{username}:2"),
                ],
                [
                    InlineKeyboardButton("🚨 紧急（绕过静音）", callback_data=f"push:{username}:3"),
                ],
            ])
            await message.reply_text(
                f"📨 通知 {member['display_name']}（@{username}）\n\n"
                f"选择通知级别：",
                reply_markup=keyboard,
            )


async def handle_push_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    if not data:
        await query.answer()
        return

    # Handle critical confirm
    if data.startswith("critical_yes:"):
        await query.answer()
        username = data.split(":")[1]
        await _do_push(query, context, username, 3)
        return

    # Handle critical cancel
    if data.startswith("critical_no:"):
        await query.answer()
        username = data.split(":")[1]
        member = get_member(username)
        name = member["display_name"] if member else username
        await query.edit_message_text(f"❌ 已取消向 {name} 发送紧急通知")
        return

    if not data.startswith("push:"):
        await query.answer()
        return

    parts = data.split(":")
    if len(parts) != 3:
        await query.answer()
        return

    _, username, level_str = parts
    try:
        level = int(level_str)
    except ValueError:
        await query.answer()
        return

    await query.answer()

    # Level 3 (critical) needs confirmation warning
    if level == 3:
        member = get_member(username)
        if not member:
            await query.edit_message_text(f"⚠️ @{username} 已被移除")
            return

        now = datetime.now()
        hour = now.hour

        # Extra warning during rest hours (22:00 - 08:00)
        if hour >= 22 or hour < 8:
            time_warning = "\n\n🌙 当前是休息时间，请三思！"
        else:
            time_warning = ""

        await query.edit_message_text(
            f"⚠️ 紧急通知确认\n\n"
            f"你即将向 {member['display_name']} 发送 🚨紧急通知：\n\n"
            f"• 绕过对方静音和勿扰模式\n"
            f"• 以最大音量持续响铃 30 秒\n"
            f"• 管理员会收到通知记录\n\n"
            f"⛔ 请确认这是真正紧急的事项\n"
            f"不要无故打扰别人休息！{time_warning}",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ 确认发送", callback_data=f"critical_yes:{username}"),
                    InlineKeyboardButton("❌ 我再想想", callback_data=f"critical_no:{username}"),
                ]
            ]),
        )
        return

    await _do_push(query, context, username, level)


async def _do_push(query, context, username, level):
    member = get_member(username)
    if not member:
        await query.edit_message_text(f"⚠️ @{username} 已被移除")
        return

    success = await push(member["bark_server"], member["bark_key"], level)
    label = LEVEL_LABELS[level]

    if success:
        log_push(username, level, query.from_user.id)
        sender_name = query.from_user.full_name or query.from_user.username or "未知"
        now = datetime.now().strftime("%H:%M")
        await query.edit_message_text(
            f"✅ 通知已发送\n\n"
            f"📨 {label} → {member['display_name']}\n"
            f"👤 发送人: {sender_name}\n"
            f"🕐 {now}"
        )

        # Notify admins for critical push
        if level == 3:
            await notify_admins_critical(
                context,
                sender=query.from_user,
                target_name=member["display_name"],
                target_username=username,
                chat=query.message.chat if query.message else None,
            )
    else:
        await query.edit_message_text(
            f"❌ 推送失败\n\n"
            f"目标: {member['display_name']}\n"
            f"请检查 Bark Key 是否正确"
        )


async def notify_admins_critical(context, sender, target_name, target_username, chat):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sender_name = sender.full_name or sender.username or str(sender.id)
    chat_title = chat.title if chat else "未知群组"

    text = (
        f"🚨 紧急推送记录\n\n"
        f"👤 发送人: {sender_name} (ID: {sender.id})\n"
        f"🎯 目标: {target_name} (@{target_username})\n"
        f"💬 群组: {chat_title}\n"
        f"🕐 时间: {now}"
    )

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=text)
        except Exception as e:
            logger.warning(f"无法通知管理员 {admin_id}: {e}")
