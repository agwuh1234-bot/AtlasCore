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
from mcp.server.fastmcp import FastMCP

from openai import OpenAI, RateLimitError

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

MAX_USER_INPUT = 6000
MAX_FILE_LINES = 250
MAX_TOOL_LOOPS = 4
MAX_OUTPUT_TOKENS = 1200

ALLOWED_USER_IDS = {
    int(x.strip())
    for x in os.environ.get(
        "ALLOWED_USER_IDS",
        "",
    ).split(",")
    if x.strip()
}


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

У тебя есть реальные GitHub-инструменты для AtlasCore.

Главные правила экономии:
- обычные вопросы решай без GitHub;
- не читай файлы без необходимости;
- большие файлы читай только нужными диапазонами строк;
- не запрашивай весь main.py, если нужен маленький участок;
- небольшие точечные изменения делай через github_replace_text;
- github_write_file используй только когда действительно нужно заменить
  файл целиком или создать новый;
- не делай лишних повторных вызовов инструментов.

Если пользователь просит проверить реальный код или репозиторий,
используй GitHub-инструменты.

Никогда не утверждай, что действие выполнено,
если инструмент вернул ошибку.

При работе с main.py не удаляй рабочие функции без необходимости.

Отвечай кратко и на языке пользователя.
"""


TOOLS = [
    {
        "type": "function",
        "name": "github_list_files",
        "description": "Показать файлы и папки AtlasCore",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Путь. Для корня используй пустую строку.",
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
        "description": (
            "Прочитать только нужный диапазон строк "
            "текстового файла AtlasCore"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Первая строка, начиная с 1",
                },
                "end_line": {
                    "type": "integer",
                    "description": (
                        "Последняя строка. "
                        "Максимум 250 строк за запрос."
                    ),
                },
            },
            "required": [
                "path",
                "start_line",
                "end_line",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "github_replace_text",
        "description": (
            "Точечно заменить один уникальный фрагмент "
            "в существующем файле и сделать commit"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                },
                "old_text": {
                    "type": "string",
                },
                "new_text": {
                    "type": "string",
                },
                "commit_message": {
                    "type": "string",
                },
            },
            "required": [
                "path",
                "old_text",
                "new_text",
                "commit_message",
            ],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "github_write_file",
        "description": (
            "Создать новый файл или полностью заменить "
            "существующий файл и сделать commit"
        ),
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
    url = (
        f"https://api.github.com/repos/"
        f"{REPO}/contents/{path}"
    )

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


async def get_github_file(path):
    url = (
        f"https://api.github.com/repos/"
        f"{REPO}/contents/{path}"
    )

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            url,
            headers=github_headers(),
        )

    return response


async def github_read_file(
    path,
    start_line,
    end_line,
):
    response = await get_github_file(path)

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

    lines = content.splitlines()

    start_line = max(
        1,
        int(start_line),
    )

    end_line = max(
        start_line,
        int(end_line),
    )

    end_line = min(
        end_line,
        start_line + MAX_FILE_LINES - 1,
    )

    selected = lines[
        start_line - 1:end_line
    ]

    numbered = "\n".join(
        f"{i}: {line}"
        for i, line in enumerate(
            selected,
            start=start_line,
        )
    )

    return json.dumps(
        {
            "ok": True,
            "path": path,
            "sha": data.get("sha"),
            "start_line": start_line,
            "end_line": min(
                end_line,
                len(lines),
            ),
            "total_lines": len(lines),
            "content": numbered[:12000],
        },
        ensure_ascii=False,
    )


async def github_write_file(
    path,
    content,
    commit_message,
):
    url = (
        f"https://api.github.com/repos/"
        f"{REPO}/contents/{path}"
    )

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
                    "error": current.text[:500],
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
            "commit_sha": (
                data.get("commit", {})
                .get("sha")
            ),
            "file_url": (
                data.get("content", {})
                .get("html_url")
            ),
        },
        ensure_ascii=False,
    )


async def github_replace_text(
    path,
    old_text,
    new_text,
    commit_message,
):
    response = await get_github_file(path)

    if response.status_code != 200:
        return json.dumps(
            {
                "ok": False,
                "status": response.status_code,
                "step": "read_existing",
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
        current_content = base64.b64decode(
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

    occurrences = current_content.count(
        old_text
    )

    if occurrences != 1:
        return json.dumps(
            {
                "ok": False,
                "error": "old_text_not_unique",
                "occurrences": occurrences,
            },
            ensure_ascii=False,
        )

    new_content = current_content.replace(
        old_text,
        new_text,
        1,
    )

    return await github_write_file(
        path,
        new_content,
        commit_message,
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
            arguments["path"],
            arguments["start_line"],
            arguments["end_line"],
        )

    if name == "github_replace_text":
        return await github_replace_text(
            arguments["path"],
            arguments["old_text"],
            arguments["new_text"],
            arguments["commit_message"],
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
            "tool": name,
        },
        ensure_ascii=False,
    )


def create_response(**kwargs):
    kwargs.setdefault(
        "max_output_tokens",
        MAX_OUTPUT_TOKENS,
    )

    return openai_client.responses.create(
        **kwargs
    )


async def run_atlas(
    text,
    previous_response_id=None,
):
    text = (text or "")[:MAX_USER_INPUT]

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

    for _ in range(MAX_TOOL_LOOPS):
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
    version="1.1",
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


def verify_user_access(
    user_id: int | None,
):
    if not ALLOWED_USER_IDS:
        return True

    if user_id is None:
        return False

    return user_id in ALLOWED_USER_IDS


@api.get("/health")
async def api_health():
    return {
        "ok": True,
        "service": "AtlasCore",
        "telegram": True,
        "openai": True,
        "github": True,
        "optimized": True,
        "private": bool(
            ALLOWED_USER_IDS
        ),
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

    except RateLimitError:
        logger.warning(
            "OpenAI rate limit reached"
        )

        raise HTTPException(
            status_code=429,
            detail=(
                "OpenAI API rate limit reached. "
                "Atlas is not broken."
            ),
        )

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
    user_id = (
        update.effective_user.id
        if update.effective_user
        else None
    )

    if not verify_user_access(
        user_id
    ):
        return

    await update.message.reply_text(
        "ATLAS ONLINE ✅\n\n"
        "Telegram: ✅\n"
        "API: ✅\n"
        "OpenAI: ✅\n"
        "GitHub READ: ✅\n"
        "GitHub WRITE: ✅\n"
        "Token optimization: ✅"
    )


async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = (
        update.effective_user.id
        if update.effective_user
        else None
    )

    if not verify_user_access(
        user_id
    ):
        return

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
        "Token optimization: ✅\n"
        f"Repo: {REPO}\n"
        f"Model: {MODEL}"
    )


async def repo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = (
        update.effective_user.id
        if update.effective_user
        else None
    )

    if not verify_user_access(
        user_id
    ):
        return

    url = (
        f"https://api.github.com/"
        f"repos/{REPO}"
    )

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
    user_id = (
        update.effective_user.id
        if update.effective_user
        else None
    )

    if not verify_user_access(
        user_id
    ):
        return

    await update.message.reply_text(
        "Telegram Atlas уже работает "
        "без накопления истории ✅"
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

    user_id = (
        update.effective_user.id
        if update.effective_user
        else None
    )

    if not verify_user_access(
        user_id
    ):
        return

    await update.message.chat.send_action(
        ChatAction.TYPING
    )

    try:
        # Telegram специально stateless:
        # previous_response_id не передаём.
        response = await run_atlas(
            update.message.text
        )

        text = (
            response.output_text or ""
        ).strip()

        if not text:
            text = (
                "Atlas выполнил запрос, "
                "но не вернул текстовый ответ."
            )

        await update.message.reply_text(
            text[:4000]
        )

    except RateLimitError:
        logger.warning(
            "Telegram OpenAI rate limit"
        )

        await update.message.reply_text(
            "Лимит OpenAI API временно "
            "достигнут. Попробуй позже — "
            "Atlas не сломан."
        )

    except Exception as exc:
        logger.exception(
            "Telegram Atlas error"
        )

        await update.message.reply_text(
            "Atlas error ❌\n"
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
        "ATLAS OPTIMIZED CORE ONLINE"
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