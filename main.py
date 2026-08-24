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

Если пользователь просит изменить или создать файл в AtlasCore:
используй github_write_file.

Никогда не утверждай, что файл изменён или создан,
если инструмент фактически не выполнил запись.

При изменении main.py будь особенно осторожен.
Не удаляй рабочие функции без явного запроса пользователя.

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
    {
        "type": "function",
        "name": "github_write_file",
        "description": "Создать новый или полностью заменить существующий текстовый файл в AtlasCore и сделать commit",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Путь к файлу, например notes.txt или main.py",
                },
                "content": {
                    "type": "string",
                    "description": "Полное новое содержимое файла",
                },
                "commit_message": {
                    "type": "string",
                    "description": "Сообщение Git commit",
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
        {
            "ok": True,
            "items": result,
        },
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

    content = content[:20000]

    return json.dumps(
        {
            "ok": True,
            "path": path,
            "content": content,
            "sha": data.get("sha"),
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

    async with httpx.AsyncClient(timeout=20) as client:
        current = await client.get(
            url,
            headers=github_headers(),
        )

        if current.status_code == 200:
            current_data = current.json()
            payload["sha"] = current_data["sha"]

        elif current.status_code != 404:
            return json.dumps({
                "ok": False,
                "status": current.status_code,
                "step": "read_existing",
            })

        response = await client.put(
            url,
            headers={
                **github_headers(),
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if response.status_code not in (200, 201):
        return json.dumps({
            "ok": False,
            "status": response.status_code,
            "body": response.text[:1000],
        })

    data = response.json()

    return json.dumps(
        {
            "ok": True,
            "path": path,
            "commit_sha": data.get(
                "commit",
                {}
            ).get("sha"),
            "html_url": data.get(
                "content",
                {}
            ).get("html_url"),
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

    if name == "github_write_file":
        return await github_write_file(
            arguments["path"],
            arguments["content"],
            arguments["commit_message"],
        )

    return json.dumps({
        "ok": False,
        "error": "unknown_tool",
    })


def create_response(**kwargs):
    return openai_client.responses.create(**kwargs)


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
        request[
            "previous_response_id"
        ] = previous_response_id

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
                    "Tool failed"
                )

                result = json.dumps({
                    "ok