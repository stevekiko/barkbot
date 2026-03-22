"""
群组通知模块 — 处理群组中的 @提醒 和推送回调

工作流程：
  1. 用户在群组中 @某成员
  2. Bot 弹出通知级别选择按钮（普通/优先/紧急）
  3. 用户点击按钮触发推送（紧急通知需二次确认）
  4. 推送成功后记录日志，紧急推送额外通知管理员
"""

import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bark import push, LEVEL_LABELS
from config import ALLOWED_GROUPS, ADMIN_IDS
from database import get_member, log_push

logger = logging.getLogger(__name__)


async def log_group_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """记录群组 ID 到日志，方便配置 ALLOWED_GROUPS 白名单"""
    chat = update.effective_chat
    if chat:
        logger.info(f"群组消息 - 群组: {chat.title} (ID: {chat.id})")


async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    处理群组中的 @提醒

    检测消息中的 @username，如果该用户已注册 Bark，
    则弹出通知级别选择按钮。仅在群组/超级群组中生效。
    """
    message = update.message
    if not message or not message.text:
        return

    chat = message.chat

    # 仅在群组/超级群组中生效，私聊不触发
    if chat.type not in ("group", "supergroup"):
        return

    # 群组白名单校验（ALLOWED_GROUPS 为空则不限制）
    if ALLOWED_GROUPS and chat.id not in ALLOWED_GROUPS:
        return

    # 从消息实体中提取所有 @提醒
    mentions = set()
    if message.entities:
        for entity in message.entities:
            if entity.type == "mention":
                # 去掉 @ 前缀，转小写
                username = message.text[entity.offset + 1 : entity.offset + entity.length].lower()
                mentions.add(username)

    if not mentions:
        return

    # 为每个已注册的被@成员弹出推送按钮
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
    """
    处理推送按钮的回调

    回调数据格式：
      - push:{username}:{level}     — 发起推送
      - critical_yes:{username}     — 确认紧急推送
      - critical_no:{username}      — 取消紧急推送
    """
    query = update.callback_query
    data = query.data
    if not data:
        await query.answer()
        return

    # 处理紧急推送确认
    if data.startswith("critical_yes:"):
        await query.answer()
        username = data.split(":")[1]
        await _do_push(query, context, username, 3)
        return

    # 处理紧急推送取消
    if data.startswith("critical_no:"):
        await query.answer()
        username = data.split(":")[1]
        member = get_member(username)
        name = member["display_name"] if member else username
        await query.edit_message_text(f"❌ 已取消向 {name} 发送紧急通知")
        return

    # 非 push: 开头的回调忽略
    if not data.startswith("push:"):
        await query.answer()
        return

    # 解析回调数据：push:{username}:{level}
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

    # 紧急通知（级别 3）需要二次确认
    if level == 3:
        member = get_member(username)
        if not member:
            await query.edit_message_text(f"⚠️ @{username} 已被移除")
            return

        now = datetime.now()
        hour = now.hour

        # 休息时段（22:00-08:00）额外警告
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

    # 普通/优先通知直接推送
    await _do_push(query, context, username, level)


async def _do_push(query, context, username, level):
    """
    执行 Bark 推送

    推送成功后记录日志；紧急推送额外通知所有管理员。
    """
    member = get_member(username)
    if not member:
        await query.edit_message_text(f"⚠️ @{username} 已被移除")
        return

    success = await push(member["bark_server"], member["bark_key"], level)
    label = LEVEL_LABELS[level]

    if success:
        # 记录推送日志
        log_push(username, level, query.from_user.id)
        sender_name = query.from_user.full_name or query.from_user.username or "未知"
        now = datetime.now().strftime("%H:%M")
        await query.edit_message_text(
            f"✅ 通知已发送\n\n"
            f"📨 {label} → {member['display_name']}\n"
            f"👤 发送人: {sender_name}\n"
            f"🕐 {now}"
        )

        # 紧急推送额外通知管理员
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
    """紧急推送后私聊通知所有管理员，记录发送人、目标、群组、时间"""
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
