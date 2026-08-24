import os
import json
import logging
import asyncio
import base64
import threading

import httpx
import uvicorn

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

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
ATLAS_API_KEY = os.environ["ATLAS_API_KEY"]

REPO = "agwuh1234-bot/AtlasCore"
MODEL = "gpt-5.4-mini"

PORT = int(os.environ.get("PORT", "8080"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("atlas")

openai_client = OpenAI(
    api_key=OPENAI_API_KEY
)

SYSTEM_PROMPT = """
Ты Atlas — персональный ИИ-ассистент и ядро автоматизации.

У тебя есть реальные инструменты GitHub для репозитория AtlasCore.

Ты умеешь:
- просматривать файлы;
- читать файлы;
- создавать новые файлы;
- полностью обновлять существующие файлы;
- делать GitHub commit.

Если пользователь спрашивает о репозитории или коде,
используй GitHub-инструменты.

Если пользователь просит создать или изменить файл,
используй github_write_file.

Никогда не говори, что действие выполнено,
если инструмент вернул ошибку.

При изменении main.py сначала прочитай текущий файл.

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
                    "description": "Путь внутри репозитория. Для корня используй пустую строку.",
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
    {
        "type": "function",
        "name": "github_write_file",
        "description": "Создать или полностью обновить текстовый файл в AtlasCore и сделать commit",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                },
                "content": {
                    "type": "string",
                },
                "commit_message": {
                    "type": "string",
                },
            },
            "required": [
                "path",
                "content",
                "commit_message",
            ],
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

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            url,
            headers=github_headers(),
        )

    if response.status_code != 200:
        return json.dumps(
            {
                "ok": False,
                "status": response.status_code,
                "error": response.text[:500],
            },
            ensure_ascii=False,
        )

    data = response.json()

    if isinstance(data, list):
        items = [
            {
                "name": item.get("name"),
                "path": item.get("path"),
                "type": item.get("type"),
            }
            for item in data
        ]
    else:
        items = [
            {
                "name": data.get("name"),
                "path": data.get("path"),
                "type": data.get("type"),
            }
        ]

    return json.dumps(
        {
            "ok": True,
            "items": items,
        },
        ensure_ascii=False,
    )


async def github_read_file(path):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            url,
            headers=github_headers(),
        )

    if response.status_code != 200:
        return json.dumps(
            {
                "ok": False,
                "status": response.status_code,
                "path": path,
            },
            ensure_ascii=False,
        )

    data = response.json()

    if data.get("type") != "file":
        return json.dumps(
            {
                "ok": False,
                "error": "not_a_file",
            },
            ensure_ascii=False,
        )

    try:
        content = base64.b64decode(
            data["content"]
        ).decode("utf-8")
    except Exception as exc:
        return json.dumps(
            {
                "ok": False,
                "error": "decode_failed",
                "details": str(exc),
            },
            ensure_ascii=False,
        )

    return json.dumps(
        {
            "ok": True,
            "path": path,
            "sha": data.get("sha"),
            "content": content[:30000],
        },
        ensure_ascii=False,
    )


async def github_write_file(
    path,
    content,
    commit_message,
):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"

    payload = {
        "message": commit_message,
        "content": base64.b64encode(
            content.encode("utf-8")
        ).decode("utf-8"),
        "branch": "main",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        current = await client.get(
            url,
            headers=github_headers(),
        )

        if current.status_code == 200:
            current_data = current.json()
            payload["sha"] = current_data["sha"]

        elif current.status_code != 404:
            return json.dumps(
                {
                    "ok": False,
                    "status": current.status_code,
                    "step": "read_existing",
                },
                ensure_ascii=False,
            )

        response = await client.put(
            url,
            headers=github_headers(),
            json=payload,
        )

    if response.status_code not in (200, 201):
        return json.dumps(
            {
                "ok": False,
                "status": response.status_code,
                "step": "write",
                "error": response.text[:1000],
            },
            ensure_ascii=False,
        )

    data = response.json()

    return json.dumps(
        {
            "ok": True,
            "path": path,
            "commit_sha": data.get(
                "commit",
                {},
            ).get("sha"),
            "file_url": data.get(
                "content",
                {},
            ).get("html_url"),
        },
        ensure_ascii=False,
    )


async def execute_tool(
    name,
    arguments,
):
    if name == "github_list_files":
        return await github_list_files(
            arguments.get("path", "")
        )

    if name == "github_read_file":
        return await github_read_file(
            arguments["path"]
        )

    if name == "github_write_file":
        return await github_write_file(
            arguments["path"],
            arguments["content"],
            arguments["commit_message"],
        )

    return json.dumps(
        {
            "ok": False,
            "error": "unknown_tool",
        },
        ensure_ascii=False,
    )


def create_response(**kwargs):
    return openai_client.responses.create(
        **kwargs
    )


async def run_atlas(
    text,
    previous_response_id=None,
):
    request = {
        "model": MODEL,
        "instructions": SYSTEM_PROMPT,
        "input": text,
        "tools": TOOLS,
        "tool_choice": "auto",
    }

    if previous_response_id:
        request["previous_response_id"] = (
            previous_response_id
        )

    response = await asyncio.to_thread(
        create_response,
        **request,
    )

    for _ in range(8):
        tool_calls = [
            item
            for item in response.output
            if getattr(
                item,
                "type",
                None,
            ) == "function_call"
        ]

        if not tool_calls:
            return response

        outputs = []

        for call in tool_calls:
            try:
                arguments = json.loads(
                    call.arguments
                )

                result = await execute_tool(
                    call.name,
                    arguments,
                )

            except Exception as exc:
                logger.exception(
                    "Tool execution failed"
                )

                result = json.dumps(
                    {
                        "ok": False,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )

            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": result,
                }
            )

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


api = FastAPI(
    title="Atlas API",
    version="1.0",
)


class TaskRequest(BaseModel):
    task: str
    previous_response_id: str | None = None


def verify_api_key(
    x_atlas_key: str | None,
):
    if x_atlas_key != ATLAS_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )


@api.get("/health")
async def api_health():
    return {
        "ok": True,
        "service": "AtlasCore",
        "telegram": True,
        "openai": True,
        "github": True,
    }


@api.post("/task")
async def api_task(
    body: TaskRequest,
    x_atlas_key: str | None = Header(
        default=None,
        alias="X-Atlas-Key",
    ),
):
    verify_api_key(
        x_atlas_key
    )

    try:
        response = await run_atlas(
            body.task,
            body.previous_response_id,
        )

        return {
            "ok": True,
            "response_id": response.id,
            "answer": response.output_text,
        }

    except Exception as exc:
        logger.exception(
            "API task failed"
        )

        raise HTTPException(
            status_code=500,
            detail=str(exc),
        )


async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "ATLAS ONLINE ✅\n\n"
        "Telegram: ✅\n"
        "API: ✅\n"
        "OpenAI: ✅\n"
        "GitHub READ: ✅\n"
        "GitHub WRITE: ✅"
    )


async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    railway = os.environ.get(
        "RAILWAY_ENVIRONMENT_NAME",
        "unknown",
    )

    await update.message.reply_text(
        "ATLAS STATUS ✅\n\n"
        "Telegram: ✅ online\n"
        f"Railway: {railway}\n"
        "API: ✅\n"
        "OpenAI: ✅\n"
        "GitHub READ: ✅\n"
        "GitHub WRITE: ✅\n"
        f"Repo: {REPO}\n"
        f"Model: {MODEL}"
    )


async def repo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    url = f"https://api.github.com/repos/{REPO}"

    async with httpx.AsyncClient(
        timeout=20
    ) as client:
        response = await client.get(
            url,
            headers=github_headers(),
        )

    if response.status_code != 200:
        await update.message.reply_text(
            f"GitHub error: "
            f"{response.status_code}"
        )
        return

    data = response.json()

    await update.message.reply_text(
        "GitHub подключён ✅\n\n"
        f"Repo: {data.get('full_name')}\n"
        f"Branch: {data.get('default_branch')}\n"
        f"Visibility: {data.get('visibility')}"
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


async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if (
        not update.message
        or not update.message.text
    ):
        return

    await update.message.chat.send_action(
        ChatAction.TYPING
    )

    try:
        previous_id = context.user_data.get(
            "previous_response_id"
        )

        response = await run_atlas(
            update.message.text,
            previous_id,
        )

        context.user_data[
            "previous_response_id"
        ] = response.id

        text = response.output_text.strip()

        if not text:
            text = (
                "Atlas выполнил запрос, "
                "но не вернул текстовый ответ."
            )

        await update.message.reply_text(
            text[:4000]
        )

    except Exception as exc:
        logger.exception(
            "Telegram Atlas error"
        )

        await update.message.reply_text(
            f"Atlas error ❌\n"
            f"{type(exc).__name__}: {exc}"
        )


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    logger.exception(
        "Telegram error",
        exc_info=context.error,
    )


def run_api():
    uvicorn.run(
        api,
        host="0.0.0.0",
        port=PORT,
        log_level="info",
    )


def main():
    logger.info(
        "ATLAS API CORE ONLINE"
    )

    api_thread = threading.Thread(
        target=run_api,
        daemon=True,
    )

    api_thread.start()

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    app.add_handler(
        CommandHandler(
            "status",
            status,
        )
    )

    app.add_handler(
        CommandHandler(
            "repo",
            repo,
        )
    )

    app.add_handler(
        CommandHandler(
            "reset",
            reset,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            message_handler,
        )
    )

    app.add_error_handler(
        error_handler
    )

    app.run_polling()


if __name__ == "__main__":
    main()