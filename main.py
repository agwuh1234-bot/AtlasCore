import os
import logging
import asyncio
import httpx

from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

REPO = "agwuh1234-bot/AtlasCore"
MODEL = "gpt-5.4-mini"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("atlas")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Ты Atlas — персональный ИИ-ассистент и ядро автоматизации.

Ты работаешь через Telegram.

Твои задачи:
- понимать запрос пользователя;
- отвечать кратко и по делу;
- помогать с кодом, бизнесом, автоматизацией и организацией задач;
- понимать, когда для задачи понадобится GitHub, Railway, Shopify или другой инструмент;
- не утверждать, что действие выполнено, если инструмент фактически его не выполнил.

Отвечай на языке пользователя.
"""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ATLAS ONLINE ✅\n\n"
        "ИИ-мозг подключён.\n"
        "Напиши мне любую задачу.\n\n"
        "/status — статус системы\n"
        "/repo — GitHub\n"
        "/reset — очистить память диалога"
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    railway = os.environ.get("RAILWAY_ENVIRONMENT_NAME", "unknown")

    await update.message.reply_text(
        "ATLAS STATUS\n\n"
        "Telegram: ✅ online\n"
        f"Railway: {railway}\n"
        "OpenAI: ✅ configured\n"
        f"GitHub: {'✅ configured' if GITHUB_TOKEN else '❌ missing'}\n"
        f"Model: {MODEL}"
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
                "GitHub ✅\n\n"
                f"Repo: {data.get('full_name')}\n"
                f"Branch: {data.get('default_branch')}\n"
                f"Visibility: {data.get('visibility')}"
            )
        else:
            await update.message.reply_text(
                f"GitHub error: {response.status_code}"
            )

    except Exception:
        logger.exception("GitHub check failed")
        await update.message.reply_text("Ошибка подключения к GitHub.")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("previous_response_id", None)
    await update.message.reply_text("Память текущего диалога очищена ✅")


def ask_openai(text: str, previous_response_id=None):
    kwargs = {
        "model": MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": text,
    }

    if previous_response_id:
        kwargs["previous_response_id"] = previous_response_id

    return openai_client.responses.create(**kwargs)


async def message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        previous_id = context.user_data.get("previous_response_id")

        response = await asyncio.to_thread(
            ask_openai,
            text,
            previous_id,
        )

        context.user_data["previous_response_id"] = response.id

        answer = response.output_text.strip()

        if not answer:
            answer = "Не удалось получить текстовый ответ."

        await update.message.reply_text(answer[:4000])

    except Exception as exc:
        logger.exception("OpenAI request failed")

        await update.message.reply_text(
            f"Ошибка ИИ: {type(exc).__name__}"
        )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.exception(
        "Telegram error",
        exc_info=context.error,
    )


def main():
    logger.info("ATLAS AI CORE ONLINE")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("repo", repo_status))
    app.add_handler(CommandHandler("reset", reset))

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

