import os
import logging
import httpx

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = "agwuh1234-bot/AtlasCore"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("atlas")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ATLAS CORE ONLINE ✅\n\n"
        "Ядро запущено.\n"
        "/status — статус системы\n"
        "/repo — проверить GitHub\n"
        "/help — команды"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Команды Atlas:\n\n"
        "/start — запуск\n"
        "/status — состояние ядра\n"
        "/repo — проверка GitHub\n"
        "/help — помощь"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    railway = os.environ.get("RAILWAY_ENVIRONMENT_NAME", "unknown")
    github = "✅ подключён" if GITHUB_TOKEN else "❌ не подключён"

    await update.message.reply_text(
        "ATLAS STATUS\n\n"
        "Telegram: ✅ online\n"
        f"Railway: {railway}\n"
        f"GitHub: {github}\n"
        f"Repo: {REPO}"
    )


async def repo_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not GITHUB_TOKEN:
        await update.message.reply_text("GITHUB_TOKEN не найден.")
        return

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"https://api.github.com/repos/{REPO}",
                headers=headers,
            )

        if response.status_code == 200:
            data = response.json()

            await update.message.reply_text(
                "GitHub подключён ✅\n\n"
                f"Repo: {data.get('full_name')}\n"
                f"Branch: {data.get('default_branch')}\n"
                f"Visibility: {data.get('visibility')}"
            )

        else:
            await update.message.reply_text(
                f"GitHub error: {response.status_code}"
            )

    except Exception as exc:
        logger.exception("GitHub check failed")

        await update.message.reply_text(
            f"GitHub check failed: {type(exc).__name__}"
        )


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    await update.message.reply_text(
        "Задачу принял ✅\n\n"
        f"{text}\n\n"
        "Atlas пока работает как базовое ядро.\n"
        "Следующий этап — подключение ИИ-мозга и инструментов."
    )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.exception(
        "Unhandled Telegram error",
        exc_info=context.error,
    )


def main():
    logger.info("ATLAS CORE ONLINE")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("repo", repo_status))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message,
        )
    )

    app.add_error_handler(error_handler)

    app.run_polling()


if __name__ == "__main__":
    main()