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
    """Global error handler — log errors, notify user, never crash."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Try to notify the user that something went wrong
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

    # Notify admin about the error
    tb = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_short = "".join(tb[-3:])[:1000]  # Last 3 frames, max 1000 chars
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
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN 未设置，请在 .env 文件中配置")
        return

    init_db()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # ── Global error handler ──
    app.add_error_handler(error_handler)

    # ── Conversation: Add member ──
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
        allow_reentry=True,
    )

    # ── Conversation: Edit member ──
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

    # /start command
    app.add_handler(CommandHandler("start", start))

    # Conversation handlers (must be before generic callback handlers)
    app.add_handler(add_conv)
    app.add_handler(edit_conv)

    # Menu callbacks
    app.add_handler(CallbackQueryHandler(menu_callback, pattern=r"^menu:(help|back)$"))
    app.add_handler(CallbackQueryHandler(show_member_list, pattern=r"^menu:list$"))
    app.add_handler(CallbackQueryHandler(test_select_member, pattern=r"^menu:test$"))

    # Admin action callbacks
    app.add_handler(CallbackQueryHandler(delete_confirm, pattern=r"^del:"))
    app.add_handler(CallbackQueryHandler(delete_execute, pattern=r"^delyes:"))
    app.add_handler(CallbackQueryHandler(test_select_level, pattern=r"^test:"))
    app.add_handler(CallbackQueryHandler(test_execute, pattern=r"^testpush:"))

    # Group push callbacks (push, critical confirm/cancel)
    app.add_handler(CallbackQueryHandler(handle_push_callback, pattern=r"^(push:|critical_yes:|critical_no:)"))

    # Log group ID for any group message
    app.add_handler(
        MessageHandler(filters.TEXT & (filters.ChatType.GROUP | filters.ChatType.SUPERGROUP), log_group_id),
        group=1,
    )

    # Group @mention listener
    app.add_handler(MessageHandler(filters.TEXT & filters.Entity("mention"), handle_mention))

    logger.info("BarkBot 已启动")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
