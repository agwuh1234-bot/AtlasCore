import os
import json
import logging
import asyncio
import base64
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
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]

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

У тебя есть реальные инструменты GitHub.

Если пользователь спрашивает о репозитории, коде или файлах:
используй инструменты, а не придумывай ответ.

Никогда не утверждай, что прочитал файл или проверил репозиторий,
если инструмент фактически не был вызван.

Сейчас GitHub работает только в режиме чтения.
Ничего не изменяй и не обещай изменить.

Отвечай на языке пользователя.
"""


TOOLS = [
    {
        "type": "function",
        "name": "github_list_files",
        "description": "Показать файлы и папки в AtlasCore",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Путь внутри репозитория. Пустая строка означает корень.",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "github_read_file",
        "description": "Прочитать текстовый файл из AtlasCore",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Например main.py или requirements.txt",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def github_list_files(path=""):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            url,
            headers=github_headers(),
        )

    if response.status_code != 200:
        return json.dumps({
            "ok": False,
            "status": response.status_code,
        })

    data = response.json()

    if isinstance(data, list):
        result = [
            {
                "name": item["name"],
                "path": item["path"],
                "type": item["type"],
            }
            for item in data
        ]
    else:
        result = {
            "name": data.get("name"),
            "path": data.get("path"),
            "type": data.get("type"),
        }

    return json.dumps(
        {"ok": True, "items": result},
        ensure_ascii=False,
    )


async def github_read_file(path):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            url,
            headers=github_headers(),
        )

    if response.status_code != 200:
        return json.dumps({
            "ok": False,
            "status": response.status_code,
            "path": path,
        })

    data = response.json()

    if data.get("type") != "file":
        return json.dumps({
            "ok": False,
            "error": "not_a_file",
        })

    try:
        content = base64.b64decode(
            data["content"]
        ).decode("utf-8")
    except Exception:
        return json.dumps({
            "ok": False,
            "error": "decode_failed",
        })

    # Защита от слишком больших ответов
    content = content[:20000]

    return json.dumps(
        {
            "ok": True,
            "path": path,
            "content": content,
        },
        ensure_ascii=False,
    )


async def execute_tool(name, arguments):
    if name == "github_list_files":
        return await github_list_files(
            arguments.get("path", "")
        )

    if name == "github_read_file":
        return await github_read_file(
            arguments["path"]
        )

    return json.dumps({
        "ok": False,
        "error": "unknown_tool",
    })


def create_response(**kwargs):
    return openai_client.responses.create(**kwargs)


async def run_atlas(text, previous_response_id=None):
    request = {
        "model": MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": text,
        "tools": TOOLS,
        "tool_choice": "auto",
    }

    if previous_response_id:
        request["previous_response_id"] = previous_response_id

    response = await asyncio.to_thread(
        create_response,
        **request,
    )

    # До нескольких последовательных действий
    for _ in range(6):
        tool_calls = [
            item
            for item in response.output
            if getattr(item, "type", None) == "function_call"
        ]

        if not tool_calls:
            return response

        outputs = []

        for call in tool_calls:
            try:
                arguments = json.loads(call.arguments)
                result = await execute_tool(
                    call.name,
                    arguments,
                )

            except Exception as exc:
                logger.exception("Tool failed")

                result = json.dumps({
                    "ok": False,
                    "error": type(exc).__name__,
                })

            outputs.append({
                "type": "function_call_output",
                "call_id": call.call_id,
                "output": result,
            })

        response = await asyncio.to_thread(
            create_response,
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            previous_response_id=response.id,
            input=outputs,
            tools=TOOLS,
            tool_choice="auto",
        )

    return response


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "ATLAS ONLINE ✅\n\n"
        "ИИ: ✅\n"
        "GitHub tools: ✅ READ\n"
        "Railway: ✅\n\n"
        "Теперь можешь спросить:\n"
        "«Какие файлы есть в AtlasCore?»\n"
        "или\n"
        "«Прочитай main.py и объясни код»"
    )


async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "ATLAS STATUS ✅\n\n"
        "Telegram: ✅\n"
        "OpenAI: ✅\n"
        "GitHub: ✅ READ\n"
        "Railway: ✅\n"
        f"Model: {MODEL}"
    )


async def reset(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.pop(
        "previous_response_id",
        None,
    )

    await update.message.reply_text(
        "Память диалога очищена ✅"
    )


async def message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = update.message.text or ""

    await update.message.chat.send_action(
        ChatAction.TYPING
    )

    try:
        previous_id = context.user_data.get(
            "previous_response_id"
        )

        response = await run_atlas(
            text,
            previous_id,
        )

        context.user_data[
            "previous_response_id"
        ] = response.id

        answer = response.output_text.strip()

        if not answer:
            answer = "Задача выполнена, но текстового ответа нет."

        await update.message.reply_text(
            answer[:4000]
        )

    except Exception as exc:
        logger.exception("Atlas failed")

        await update.message.reply_text(
            f"Ошибка Atlas: {type(exc).__name__}"
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
    logger.info("ATLAS TOOL CORE ONLINE")

    app = Application.builder().token(
        BOT_TOKEN
    ).build()

    app.add_handler(
        CommandHandler("start", start)
    )
    app.add_handler(
        CommandHandler("status", status)
    )
    app.add_handler(
        CommandHandler("reset", reset)
    )

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