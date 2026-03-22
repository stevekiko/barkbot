"""
BarkBot 入口模块

注册所有 handler，启动 Telegram Bot 轮询。
包含全局错误处理，异常时通知用户重试并向管理员发送错误详情。
"""

import html
import logging
import traceback

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

from config import BOT_TOKEN, ADMIN_IDS
from database import init_db
from handlers.start import start, menu_callback
from handlers.admin import (
    add_start, input_username, input_display_name, input_bark_key, cancel_conversation,
    show_member_list, delete_confirm, delete_execute,
    test_select_member, test_select_level, test_execute,
    edit_member_menu, edit_select_field, edit_input_value,
    INPUT_USERNAME, INPUT_DISPLAY_NAME, INPUT_BARK_KEY, EDIT_VALUE,
)
from handlers.notify import handle_mention, handle_push_callback, log_group_id

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """
    全局错误处理器

    捕获所有未处理的异常，确保 Bot 不会崩溃：
    1. 记录错误日志
    2. 通知用户操作出错
    3. 向管理员发送错误详情（包含堆栈信息）
    """
    logger.error("处理更新时发生异常:", exc_info=context.error)

    # 尝试通知触发错误的用户
    try:
        if isinstance(update, Update):
            if update.callback_query:
                try:
                    await update.callback_query.answer("⚠️ 操作出错，请重试", show_alert=True)
                except Exception:
                    pass
            elif update.message:
                try:
                    await update.message.reply_text("⚠️ 处理出错，请重试")
                except Exception:
                    pass
    except Exception:
        pass

    # 向管理员发送错误报告
    tb = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_short = "".join(tb[-3:])[:1000]  # 取最后 3 帧，限制 1000 字符
    error_msg = (
        f"🐛 Bot 异常\n\n"
        f"错误: {html.escape(str(context.error))}\n\n"
        f"<pre>{html.escape(tb_short)}</pre>"
    )
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=error_msg,
                parse_mode="HTML",
            )
        except Exception:
            pass


def main():
    """Bot 主函数，注册所有 handler 并启动轮询"""

    if not BOT_TOKEN:
        logger.error("BOT_TOKEN 未设置，请在 .env 文件中配置")
        return

    # 初始化数据库（创建表）
    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ── 全局错误处理 ──
    app.add_error_handler(error_handler)

    # ── 会话：添加成员（分步引导） ──
    # 流程：点击"添加成员" → 输入用户名 → 输入显示名称 → 输入 Bark Key
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_start, pattern=r"^menu:add$")],
        states={
            INPUT_USERNAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_username),
            ],
            INPUT_DISPLAY_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_display_name),
            ],
            INPUT_BARK_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, input_bark_key),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_conversation, pattern=r"^conv:cancel$"),
            CallbackQueryHandler(show_member_list, pattern=r"^menu:list$"),
            CallbackQueryHandler(cancel_conversation, pattern=r"^menu:back$"),
        ],
        per_message=False,
        allow_reentry=True,  # 允许重复进入，防止会话卡死
    )

    # ── 会话：编辑成员信息 ──
    # 流程：点击"编辑" → 选择字段（名称/Bark Key） → 输入新值
    edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_member_menu, pattern=r"^edit:")],
        states={
            EDIT_VALUE: [
                CallbackQueryHandler(edit_select_field, pattern=r"^editfield:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_input_value),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_conversation, pattern=r"^conv:cancel$"),
            CallbackQueryHandler(show_member_list, pattern=r"^menu:list$"),
            CallbackQueryHandler(cancel_conversation, pattern=r"^menu:back$"),
        ],
        per_message=False,
        allow_reentry=True,
    )

    # ── 注册 handler（注意顺序，会话 handler 必须在通用回调之前） ──

    # /start 命令 — 打开管理面板
    app.add_handler(CommandHandler("start", start))

    # 会话 handler（添加 / 编辑成员）
    app.add_handler(add_conv)
    app.add_handler(edit_conv)

    # 菜单导航回调（帮助 / 返回主菜单）
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:(help|back)$"))
    # 成员列表
    app.add_handler(CallbackQueryHandler(show_member_list, pattern=r"^menu:list$"))
    # 测试推送入口
    app.add_handler(CallbackQueryHandler(test_select_member, pattern=r"^menu:test$"))

    # 管理操作回调
    app.add_handler(CallbackQueryHandler(delete_confirm, pattern=r"^del:"))      # 删除确认
    app.add_handler(CallbackQueryHandler(delete_execute, pattern=r"^delyes:"))    # 执行删除
    app.add_handler(CallbackQueryHandler(test_select_level, pattern=r"^test:"))   # 选择测试级别
    app.add_handler(CallbackQueryHandler(test_execute, pattern=r"^testpush:"))    # 执行测试推送

    # 群组推送回调（普通推送 / 紧急确认 / 紧急取消）
    app.add_handler(CallbackQueryHandler(handle_push_callback, pattern=r"^(push:|critical_yes:|critical_no:)"))

    # 群组消息监听 — 记录群组 ID 到日志（用于获取群组 ID）
    # group=1 表示独立处理组，不影响其他 handler
    app.add_handler(
        MessageHandler(filters.TEXT & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP), log_group_id),
        group=1,
    )

    # 群组 @提醒监听 — 检测 @成员 并弹出推送按钮
    app.add_handler(MessageHandler(filters.TEXT & filters.Entity("mention"), handle_mention))

    logger.info("BarkBot 已启动")
    # drop_pending_updates=True: 启动时丢弃积压消息，避免重启后连环处理旧消息
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
