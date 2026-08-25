import os
import re
import secrets
import json
import hmac
import hashlib
import logging
import asyncio
import base64
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import uvicorn

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from mcp.server.fastmcp import FastMCP
from openai import OpenAI, RateLimitError

from atlas_router import BudgetController, ModelRouter, response_usage, response_web_calls
from atlas_store import AtlasStore, AtlasStoreError, BudgetExceeded, TooManyJobs
from atlas_knowledge import (
    MEMORY_POLICY,
    SHOPIFY_PLAYBOOK,
    PERMISSION_LEVELS,
    memory_candidates,
    plugin_registry,
    seed_project_knowledge,
    system_registry,
)

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


for _env_name in ("BOT_TOKEN", "OPENAI_API_KEY", "GITHUB_TOKEN", "ATLAS_API_KEY", "ATLAS_BRIDGE_KEY", "ATLAS_APP_KEY"):
    if not os.environ.get(_env_name):
        raise RuntimeError(f"Missing required env: {_env_name}")

BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ATLAS_API_KEY = os.environ["ATLAS_API_KEY"]
ATLAS_BRIDGE_KEY = os.environ["ATLAS_BRIDGE_KEY"]
ATLAS_APP_KEY = os.environ["ATLAS_APP_KEY"]
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
GITHUB_BRANCH = os.environ.get("GITHUB_BRANCH", "main")

REPO = "agwuh1234-bot/AtlasCore"
PORT = int(os.environ.get("PORT", "8080"))

MAX_USER_INPUT = 6000
MAX_FILE_LINES = 250
MAX_TOOL_LOOPS = 8
MAX_OUTPUT_TOKENS = 1200

ALLOWED_USER_IDS = {
    int(x.strip())
    for x in os.environ.get("ALLOWED_USER_IDS", "").split(",")
    if x.strip()
}


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("atlas")
openai_client = OpenAI(api_key=OPENAI_API_KEY)
APP_JOB_MAX_ACTIVE = 3
APP_JOB_RETENTION = int(os.environ.get("ATLAS_JOB_RETENTION_DAYS", "180")) * 24 * 3600
APP_SESSION_MAX_AGE = 30 * 24 * 3600
APP_ATTACHMENT_MAX_COUNT = 4
APP_ATTACHMENT_MAX_DATA_CHARS = 7_000_000
MAX_APP_BODY_BYTES = 32 * 1024 * 1024

MODEL_ROUTER = ModelRouter()
MODEL = MODEL_ROUTER.fast_model
STORE = AtlasStore(max_active_jobs=APP_JOB_MAX_ACTIVE)
BUDGET = BudgetController(STORE, openai_client)
APP_JOB_TASKS = {}
APP_JOB_WORKER = None
APP_SHUTTING_DOWN = False
WORKER_ID = os.environ.get("RAILWAY_REPLICA_ID") or f"worker-{uuid.uuid4().hex[:12]}"


def secure_key_match(provided: str | None, expected: str) -> bool:
    return bool(provided) and secrets.compare_digest(provided, expected)


def app_session_token() -> str:
    ts=str(int(time.time())); nonce=secrets.token_urlsafe(16); payload=f'{ts}.{nonce}'; signature=hmac.new(ATLAS_APP_KEY.encode('utf-8'),payload.encode('utf-8'),hashlib.sha256).hexdigest(); return f'{payload}.{signature}'


def app_session_token_valid(token):
    if not token:
        return False
    try:
        ts,nonce,signature=token.split('.',2)
        payload=f'{ts}.{nonce}'
        expected=hmac.new(ATLAS_APP_KEY.encode('utf-8'),payload.encode('utf-8'),hashlib.sha256).hexdigest()
        if not secrets.compare_digest(signature,expected):
            return False
        ts_int=int(ts)
        now=int(time.time())
        return ts_int <= now + 300 and 0 <= now - ts_int <= APP_SESSION_MAX_AGE
    except Exception:
        return False



SYSTEM_PROMPT = """
Ð¢Ñ Atlas â Ð¿ÐµÑÑÐ¾Ð½Ð°Ð»ÑÐ½ÑÐ¹ ÐÐ-Ð°ÑÑÐ¸ÑÑÐµÐ½Ñ Ð¸ ÑÐ´ÑÐ¾ Ð°Ð²ÑÐ¾Ð¼Ð°ÑÐ¸Ð·Ð°ÑÐ¸Ð¸.

Ð£ ÑÐµÐ±Ñ ÐµÑÑÑ ÑÐµÐ°Ð»ÑÐ½ÑÐµ GitHub-Ð¸Ð½ÑÑÑÑÐ¼ÐµÐ½ÑÑ Ð´Ð»Ñ AtlasCore.

ÐÐ»Ð°Ð²Ð½ÑÐµ Ð¿ÑÐ°Ð²Ð¸Ð»Ð°:
- Ð¾Ð±ÑÑÐ½ÑÐµ Ð²Ð¾Ð¿ÑÐ¾ÑÑ ÑÐµÑÐ°Ð¹ Ð±ÐµÐ· GitHub;
- Ð½Ðµ ÑÐ¸ÑÐ°Ð¹ ÑÐ°Ð¹Ð»Ñ Ð±ÐµÐ· Ð½ÐµÐ¾Ð±ÑÐ¾Ð´Ð¸Ð¼Ð¾ÑÑÐ¸;
- Ð±Ð¾Ð»ÑÑÐ¸Ðµ ÑÐ°Ð¹Ð»Ñ ÑÐ¸ÑÐ°Ð¹ ÑÐ¾Ð»ÑÐºÐ¾ Ð½ÑÐ¶Ð½ÑÐ¼Ð¸ Ð´Ð¸Ð°Ð¿Ð°Ð·Ð¾Ð½Ð°Ð¼Ð¸ ÑÑÑÐ¾Ðº;
- Ð½ÐµÐ±Ð¾Ð»ÑÑÐ¸Ðµ Ð¸Ð·Ð¼ÐµÐ½ÐµÐ½Ð¸Ñ Ð´ÐµÐ»Ð°Ð¹ ÑÐ¾ÑÐµÑÐ½Ð¾;
- Ð½Ðµ Ð´ÐµÐ»Ð°Ð¹ Ð»Ð¸ÑÐ½Ð¸Ñ Ð¿Ð¾Ð²ÑÐ¾ÑÐ½ÑÑ Ð²ÑÐ·Ð¾Ð²Ð¾Ð² Ð¸Ð½ÑÑÑÑÐ¼ÐµÐ½ÑÐ¾Ð²;
- ÐµÑÐ»Ð¸ Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ Ð¿ÑÐ¾ÑÐ¸Ñ Ð¿ÑÐ¾Ð²ÐµÑÐ¸ÑÑ ÑÐµÐ°Ð»ÑÐ½ÑÐ¹ ÐºÐ¾Ð´ Ð¸Ð»Ð¸ ÑÐµÐ¿Ð¾Ð·Ð¸ÑÐ¾ÑÐ¸Ð¹,
  Ð¸ÑÐ¿Ð¾Ð»ÑÐ·ÑÐ¹ GitHub-Ð¸Ð½ÑÑÑÑÐ¼ÐµÐ½ÑÑ;
- Ð½Ð¸ÐºÐ¾Ð³Ð´Ð° Ð½Ðµ ÑÑÐ²ÐµÑÐ¶Ð´Ð°Ð¹, ÑÑÐ¾ Ð´ÐµÐ¹ÑÑÐ²Ð¸Ðµ Ð²ÑÐ¿Ð¾Ð»Ð½ÐµÐ½Ð¾, ÐµÑÐ»Ð¸ Ð¸Ð½ÑÑÑÑÐ¼ÐµÐ½Ñ Ð²ÐµÑÐ½ÑÐ» Ð¾ÑÐ¸Ð±ÐºÑ;
- Ð¿ÑÐ¸ ÑÐ°Ð±Ð¾ÑÐµ Ñ main.py Ð½Ðµ ÑÐ´Ð°Ð»ÑÐ¹ ÑÐ°Ð±Ð¾ÑÐ¸Ðµ ÑÑÐ½ÐºÑÐ¸Ð¸ Ð±ÐµÐ· Ð½ÐµÐ¾Ð±ÑÐ¾Ð´Ð¸Ð¼Ð¾ÑÑÐ¸;
- Ð¿Ð¾ÑÐ»Ðµ Ð¸ÑÐ¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°Ð½Ð¸Ñ Ð¸Ð½ÑÑÑÑÐ¼ÐµÐ½ÑÐ¾Ð² Ð¾Ð±ÑÐ·Ð°ÑÐµÐ»ÑÐ½Ð¾ Ð²ÐµÑÐ½Ð¸ Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ
  Ð½Ð¾ÑÐ¼Ð°Ð»ÑÐ½ÑÐ¹ ÑÐµÐºÑÑÐ¾Ð²ÑÐ¹ Ð¸ÑÐ¾Ð³.
- Use claude_ask for a useful second opinion on complex coding, architecture, debugging, or reasoning. Do not call Claude for simple requests.

ÐÑÐ²ÐµÑÐ°Ð¹ ÐºÑÐ°ÑÐºÐ¾ Ð¸ Ð½Ð° ÑÐ·ÑÐºÐµ Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ.
"""

SYSTEM_PROMPT = """Ты Atlas — персональный ИИ-ассистент и оркестратор.
Отвечай на языке пользователя.
Тебе передаётся текущий проект и его долговременная память. Не смешивай контекст разных проектов.
Используй memory_search, когда прошлые решения, предпочтения или текущие задачи могут изменить ответ.
Используй memory_remember только для устойчивых решений, предпочтений и фактов проекта; не сохраняй секреты.
Используй web_search только для свежей публичной информации, когда этот инструмент доступен.
Используй claude_ask, когда пользователь прямо просит Claude или независимое второе мнение заметно улучшит сложный анализ. Не вызывай Claude для простых запросов.
GitHub read tools предназначены для чтения; github_replace_text/github_write_file изменяют репозиторий и могут отсутствовать без разрешения записи.
Не утверждай успех при ошибке инструмента.
После инструментов всегда верни краткий понятный итог."""

TOOLS = [
    {
        "type": "function",
        "name": "github_list_files",
        "description": "ÐÐ¾ÐºÐ°Ð·Ð°ÑÑ ÑÐ°Ð¹Ð»Ñ Ð¸ Ð¿Ð°Ð¿ÐºÐ¸ AtlasCore",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "ÐÑÑÑ. ÐÐ»Ñ ÐºÐ¾ÑÐ½Ñ Ð¸ÑÐ¿Ð¾Ð»ÑÐ·ÑÐ¹ Ð¿ÑÑÑÑÑ ÑÑÑÐ¾ÐºÑ.",
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
        "description": "ÐÑÐ¾ÑÐ¸ÑÐ°ÑÑ Ð´Ð¸Ð°Ð¿Ð°Ð·Ð¾Ð½ ÑÑÑÐ¾Ðº ÑÐµÐºÑÑÐ¾Ð²Ð¾Ð³Ð¾ ÑÐ°Ð¹Ð»Ð° AtlasCore",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "start_line": {
                    "type": "integer",
                    "description": "ÐÐµÑÐ²Ð°Ñ ÑÑÑÐ¾ÐºÐ°, Ð½Ð°ÑÐ¸Ð½Ð°Ñ Ñ 1",
                },
                "end_line": {
                    "type": "integer",
                    "description": "ÐÐ¾ÑÐ»ÐµÐ´Ð½ÑÑ ÑÑÑÐ¾ÐºÐ°. ÐÐ°ÐºÑÐ¸Ð¼ÑÐ¼ 250 ÑÑÑÐ¾Ðº.",
                },
            },
            "required": ["path", "start_line", "end_line"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "github_replace_text",
        "description": "ÐÐ°Ð¼ÐµÐ½Ð¸ÑÑ Ð¾Ð´Ð¸Ð½ ÑÐ½Ð¸ÐºÐ°Ð»ÑÐ½ÑÐ¹ ÑÑÐ°Ð³Ð¼ÐµÐ½Ñ Ð¸ ÑÐ´ÐµÐ»Ð°ÑÑ commit",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
                "commit_message": {"type": "string"},
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
        "description": "Ð¡Ð¾Ð·Ð´Ð°ÑÑ Ð¸Ð»Ð¸ Ð¿Ð¾Ð»Ð½Ð¾ÑÑÑÑ Ð·Ð°Ð¼ÐµÐ½Ð¸ÑÑ ÑÐ°Ð¹Ð» Ð¸ ÑÐ´ÐµÐ»Ð°ÑÑ commit",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "commit_message": {"type": "string"},
            },
            "required": ["path", "content", "commit_message"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "claude_ask",
        "description": "Попросить Claude сделать второе мнение, ревью кода или сложный анализ.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

TOOLS.extend([
    {
        "type": "function",
        "name": "memory_search",
        "description": "Найти решения, предпочтения и факты в памяти текущего проекта.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
            },
            "required": ["query", "limit"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "memory_remember",
        "description": "Сохранить устойчивое решение, предпочтение или факт в памяти текущего проекта. Не сохранять секреты.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "kind": {
                    "type": "string",
                    "enum": ["decision", "preference", "fact", "task", "note"],
                },
            },
            "required": ["content", "kind"],
            "additionalProperties": False,
        },
        "strict": True,
    },
])

_TOOL_DESCRIPTIONS = {
    'github_list_files': 'Показать файлы и папки репозитория AtlasCore.',
    'github_read_file': 'Прочитать указанный диапазон строк текстового файла AtlasCore.',
    'github_replace_text': 'Точечно заменить один уникальный фрагмент текста в файле и создать commit. Использовать для небольших безопасных изменений.',
    'github_write_file': 'Создать новый файл или полностью заменить существующий файл и создать commit. Не использовать для main.py.',
    'claude_ask': 'Попросить Claude дать независимое второе мнение, ревью кода или сложный анализ. Не использовать для простых задач.',
    'memory_search': 'Найти релевантный контекст в памяти текущего проекта.',
    'memory_remember': 'Сохранить устойчивый факт в памяти текущего проекта. Не сохранять секреты.',
}
for _tool in TOOLS:
    if _tool.get('type') == 'function' and _tool.get('name') in _TOOL_DESCRIPTIONS:
        _tool['description'] = _TOOL_DESCRIPTIONS[_tool['name']]
        if _tool['name'] == 'github_list_files':
            _tool['parameters']['properties']['path']['description'] = 'Путь внутри репозитория. Для корня используйте пустую строку.'
        elif _tool['name'] == 'github_read_file':
            _tool['parameters']['properties']['start_line']['description'] = 'Первая строка, начиная с 1.'
            _tool['parameters']['properties']['end_line']['description'] = 'Последняя строка. Максимум 250 строк за один вызов.'


def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def github_list_files(path=""):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=github_headers())

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

    return json.dumps({"ok": True, "items": items}, ensure_ascii=False)


async def get_github_file(path, ref=None):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    params = {"ref": ref} if ref else None

    async with httpx.AsyncClient(timeout=20) as client:
        return await client.get(url, headers=github_headers(), params=params)


async def ask_claude(prompt: str):
    if not ANTHROPIC_API_KEY:
        return json.dumps({"ok": False, "error": "Claude API key is not configured"}, ensure_ascii=False)

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": CLAUDE_MODEL,
                    "max_tokens": 1200,
                    "system": "Ты Claude внутри Atlas. Дай независимое, полезное второе мнение. Отвечай на языке запроса.",
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            data = response.json()
            text = "\n".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            )
            return json.dumps({"ok": True, "model": CLAUDE_MODEL, "answer": text}, ensure_ascii=False)
    except Exception:
        logger.exception("Claude request failed")
        return json.dumps({"ok": False, "error": "Claude request failed"}, ensure_ascii=False)


async def github_read_file(path, start_line, end_line):
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
            {"ok": False, "error": "not_a_file"},
            ensure_ascii=False,
        )

    try:
        content = base64.b64decode(data["content"]).decode("utf-8")
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
    start_line = max(1, int(start_line))
    end_line = max(start_line, int(end_line))
    end_line = min(end_line, start_line + MAX_FILE_LINES - 1)

    selected = lines[start_line - 1 : end_line]
    numbered = "\n".join(
        f"{i}: {line}"
        for i, line in enumerate(selected, start=start_line)
    )

    return json.dumps(
        {
            "ok": True,
            "path": path,
            "sha": data.get("sha"),
            "start_line": start_line,
            "end_line": min(end_line, len(lines)),
            "total_lines": len(lines),
            "content": numbered[:12000],
        },
        ensure_ascii=False,
    )


async def github_write_file(path, content, commit_message):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"

    payload = {
        "message": commit_message,
        "content": base64.b64encode(
            content.encode("utf-8")
        ).decode("utf-8"),
        "branch": GITHUB_BRANCH,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        current = await client.get(
            url,
            headers=github_headers(),
            params={"ref": GITHUB_BRANCH},
        )

        if current.status_code == 200:
            payload["sha"] = current.json()["sha"]
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

    if response.status_code == 409:
        return json.dumps(
            {
                "ok": False,
                "status": 409,
                "step": "write",
                "error": "conflict",
            },
            ensure_ascii=False,
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
            "commit_sha": data.get("commit", {}).get("sha"),
            "file_url": data.get("content", {}).get("html_url"),
        },
        ensure_ascii=False,
    )


async def github_replace_text(
    path,
    old_text,
    new_text,
    commit_message,
):
    response = await get_github_file(path, GITHUB_BRANCH)

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
            {"ok": False, "error": "not_a_file"},
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

    occurrences = current_content.count(old_text)

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


async def claude_ask(prompt):
    if not ANTHROPIC_API_KEY:
        return json.dumps({"ok": False, "error": "claude_not_configured"}, ensure_ascii=False)
    headers = {"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}
    payload = {"model": CLAUDE_MODEL, "max_tokens": 1200, "system": "Ты Claude внутри Atlas. Дай независимое полезное второе мнение. Отвечай на языке запроса.", "messages": [{"role": "user", "content": (prompt or "")[:12000]}]}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        if response.status_code != 200:
            return json.dumps({"ok": False, "error": "claude_api_error", "status": response.status_code}, ensure_ascii=False)
        data = response.json()
        answer = "\n".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text").strip()
        return json.dumps({"ok": True, "model": data.get("model", CLAUDE_MODEL), "answer": answer}, ensure_ascii=False)
    except Exception:
        logger.exception("Claude API failed")
        return json.dumps({"ok": False, "error": "claude_request_failed"}, ensure_ascii=False)

async def execute_tool(name, arguments, run_context=None):
    run_context = run_context or {}
    project_id = run_context.get("project_id", "project-general")
    job_id = run_context.get("job_id")
    started = time.perf_counter()
    ensure_store()

    try:
        if name == "github_list_files":
            result = await github_list_files(arguments.get("path", ""))
        elif name == "github_read_file":
            result = await github_read_file(
                arguments["path"],
                arguments["start_line"],
                arguments["end_line"],
            )
        elif name == "github_replace_text":
            result = await github_replace_text(
                arguments["path"],
                arguments["old_text"],
                arguments["new_text"],
                arguments["commit_message"],
            )
        elif name == "github_write_file":
            result = await github_write_file(
                arguments["path"],
                arguments["content"],
                arguments["commit_message"],
            )
        elif name == "claude_ask":
            if not BUDGET.allow_claude():
                result = json.dumps(
                    {"ok": False, "error": "claude_daily_limit_reached"},
                    ensure_ascii=False,
                )
            else:
                result = await claude_ask(arguments["prompt"])
                BUDGET.record_claude(job_id, project_id, CLAUDE_MODEL)
        elif name == "memory_search":
            memories = STORE.search_memories(
                project_id,
                arguments.get("query", ""),
                arguments.get("limit", 8),
            )
            result = json.dumps({"ok": True, "memories": memories}, ensure_ascii=False)
        elif name == "memory_remember":
            memory = STORE.remember(
                project_id,
                arguments["content"],
                arguments.get("kind", "note"),
            )
            result = json.dumps(
                {
                    "ok": True,
                    "memory": {
                        "id": memory.get("id"),
                        "kind": memory.get("kind"),
                        "content": memory.get("content"),
                    },
                },
                ensure_ascii=False,
            )
        else:
            result = json.dumps(
                {"ok": False, "error": "unknown_tool", "tool": name},
                ensure_ascii=False,
            )
    except Exception as exc:
        STORE.record_action(
            tool=name,
            status="error",
            job_id=job_id,
            project_id=project_id,
            detail={"error_type": type(exc).__name__},
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        raise

    parsed = None
    try:
        parsed = json.loads(result) if isinstance(result, str) else result
    except (TypeError, ValueError):
        pass
    ok = not isinstance(parsed, dict) or parsed.get("ok", True)
    STORE.record_action(
        tool=name,
        status="success" if ok else "error",
        job_id=job_id,
        project_id=project_id,
        detail={"argument_keys": sorted(arguments.keys())},
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return result

def create_response(**kwargs):
    kwargs.setdefault("max_output_tokens", MAX_OUTPUT_TOKENS)
    return openai_client.responses.create(**kwargs)


@dataclass
class AtlasRunResult:
    id: str
    output_text: str
    model: str
    route: str
    usage: dict


def ensure_store():
    if not STORE.initialized:
        STORE.initialize()


def _previous_response_error(exc):
    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "previous_response_id",
            "previous response",
            "response not found",
            "conversation",
        )
    )


def _model_error(exc):
    status = getattr(exc, "status_code", None)
    message = str(exc).lower()
    return status in {400, 403, 404} and any(
        marker in message for marker in ("model", "access", "not found")
    )


async def _create_with_recovery(request):
    current = dict(request)
    for _ in range(3):
        try:
            response = await asyncio.to_thread(create_response, **current)
            return response, current["model"]
        except Exception as exc:
            if current.get("previous_response_id") and _previous_response_error(exc):
                current.pop("previous_response_id", None)
                continue
            if current.get("model") != MODEL_ROUTER.fallback_model and _model_error(exc):
                current["model"] = MODEL_ROUTER.fallback_model
                continue
            raise
    raise RuntimeError("Atlas response recovery exhausted")


def _project_instructions(project_id, text):
    project = STORE.ensure_project(project_id)
    memory = STORE.memory_context(project_id, text)
    recent = STORE.list_recent_jobs(project_id, limit=8)
    history_lines = []
    for job in recent:
        payload = job.get("payload") or {}
        task = str(payload.get("task") or "")[:500]
        answer = str(job.get("answer") or "")[:700]
        if task:
            history_lines.append(f"User: {task}")
        if answer:
            history_lines.append(f"Atlas: {answer}")
    sections = [
        SYSTEM_PROMPT,
        MEMORY_POLICY,
        f"\nТекущий проект: {project.get('name', project_id)} ({project_id}).",
    ]
    project_name = str(project.get("name") or "").lower()
    if project_id == "project-shopify" or "shopify" in project_name or "шоп" in project_name:
        sections.append("\nСпециализация проекта:\n" + SHOPIFY_PLAYBOOK)
    if memory:
        sections.append("\nДолговременная память проекта:\n" + memory)
    if history_lines:
        sections.append("\nНедавние завершённые задачи проекта:\n" + "\n".join(history_lines))
    return "\n".join(sections)


async def run_atlas(
    text,
    previous_response_id=None,
    allow_writes=True,
    attachments=None,
    claude_review=False,
    project_id="project-general",
    job_id=None,
):
    ensure_store()
    text = (text or "")[:MAX_USER_INPUT]
    attachments = attachments or []
    project_id = STORE._project_id(project_id)
    route = MODEL_ROUTER.select(
        text,
        has_attachments=bool(attachments),
        claude_review=claude_review,
    )

    selected_tools = list(TOOLS) if allow_writes else [
        tool for tool in TOOLS
        if not (
            tool.get("type") == "function"
            and tool.get("name") in {"github_replace_text", "github_write_file"}
        )
    ]
    if not ANTHROPIC_API_KEY:
        selected_tools = [
            tool for tool in selected_tools
            if not (
                tool.get("type") == "function"
                and tool.get("name") == "claude_ask"
            )
        ]
    if route.use_web:
        selected_tools.append({"type": "web_search"})

    if attachments:
        content = [{"type": "input_text", "text": text}]
        for item in attachments[:APP_ATTACHMENT_MAX_COUNT]:
            if (item.media_type or "").startswith("image/"):
                content.append({"type": "input_image", "image_url": item.data})
            else:
                content.append(
                    {
                        "type": "input_file",
                        "filename": item.name,
                        "file_data": item.data,
                    }
                )
        atlas_input = [{"role": "user", "content": content}]
    else:
        atlas_input = text

    instructions = _project_instructions(project_id, text)
    if claude_review and ANTHROPIC_API_KEY:
        instructions += (
            "\nПеред финальным ответом обязательно вызови claude_ask для "
            "независимой проверки решения, затем учти замечания Claude."
        )

    reservation = await asyncio.to_thread(
        BUDGET.reserve,
        job_id=job_id,
        model=route.model,
        input_data=atlas_input,
        instructions=instructions,
        tools=selected_tools,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        use_web=route.use_web,
    )
    request = {
        "model": route.model,
        "instructions": instructions,
        "input": atlas_input,
        "tools": selected_tools,
        "tool_choice": "auto",
    }
    if previous_response_id:
        request["previous_response_id"] = previous_response_id

    total_input_tokens = 0
    total_output_tokens = 0
    total_web_calls = 0
    used_model = route.model
    run_context = {
        "project_id": project_id,
        "job_id": job_id,
        "route": route.lane,
    }

    try:
        response, used_model = await _create_with_recovery(request)
        input_tokens, output_tokens = response_usage(response)
        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        total_web_calls += response_web_calls(response)

        claude_used = False
        for loop_index in range(MAX_TOOL_LOOPS):
            tool_calls = [
                item
                for item in response.output
                if getattr(item, "type", None) == "function_call"
            ]
            if not tool_calls:
                break

            outputs = []
            for call in tool_calls:
                try:
                    if call.name == "claude_ask" and claude_used:
                        result = json.dumps(
                            {"ok": False, "error": "claude_call_limit_reached"},
                            ensure_ascii=False,
                        )
                    else:
                        if call.name == "claude_ask":
                            claude_used = True
                        arguments = json.loads(call.arguments)
                        result = await execute_tool(
                            call.name,
                            arguments,
                            run_context=run_context,
                        )
                except Exception:
                    logger.exception("Tool execution failed")
                    result = json.dumps(
                        {
                            "ok": False,
                            "error": "Atlas error",
                            "details": "Внутренняя ошибка. Попробуйте еще раз.",
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

            last_loop = loop_index == MAX_TOOL_LOOPS - 1
            response = await asyncio.to_thread(
                create_response,
                model=used_model,
                instructions=instructions,
                previous_response_id=response.id,
                input=outputs,
                tools=selected_tools,
                tool_choice="none" if last_loop else "auto",
            )
            input_tokens, output_tokens = response_usage(response)
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            total_web_calls += response_web_calls(response)

        output_text = (response.output_text or "").strip()
        explicit_memory = re.match(
            r"^\s*(?:запомни|remember)\b[\s:,-]*(.+)$",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if explicit_memory and explicit_memory.group(1).strip():
            STORE.remember(project_id, explicit_memory.group(1).strip(), "note")
        for memory_kind, memory_content in memory_candidates(text):
            STORE.remember(project_id, memory_content, memory_kind)

        try:
            actual_cost = await asyncio.to_thread(
                BUDGET.complete,
                reservation,
                job_id=job_id,
                project_id=project_id,
                model=used_model,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                web_calls=total_web_calls,
            )
        except Exception:
            logger.exception("Failed to record Atlas usage")
            actual_cost = 0.0

        return AtlasRunResult(
            id=response.id,
            output_text=output_text,
            model=used_model,
            route=route.lane,
            usage={
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "web_calls": total_web_calls,
                "cost_usd": round(actual_cost, 6),
                "estimated_cost_usd": round(reservation.estimated_cost_usd, 6),
            },
        )
    except BaseException:
        await asyncio.to_thread(BUDGET.release, reservation)
        raise

def secure_key_match(provided: str | None, expected: str) -> bool:
    return bool(provided) and secrets.compare_digest(provided, expected)


# ---------------- MCP BRIDGE ----------------

mcp = FastMCP(
    "AtlasCore",
    host="0.0.0.0",
    stateless_http=True,
    json_response=True,
    streamable_http_path="/",
)


@mcp.tool()
async def atlas_task(
    task: str,
    previous_response_id: str | None = None,
) -> dict:
    """Send a task to Atlas. HTTP Bearer auth is enforced before tool calls."""
    try:
        response = await run_atlas(
            task,
            previous_response_id,
        )

        answer = (response.output_text or "").strip()

        return {
            "ok": True,
            "response_id": response.id,
            "answer": answer,
        }

    except Exception:
        logger.exception("MCP Atlas task failed")

        return {
            "ok": False,
            "error": "Internal server error",
        }


raw_mcp_app = mcp.streamable_http_app()

async def mcp_auth_app(scope, receive, send):
    if scope.get("type") == "http":
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode("latin-1")
        if not secure_key_match(auth_header, f"Bearer {ATLAS_API_KEY}"):
            body = b'{"detail":"Unauthorized"}'
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"www-authenticate", b"Bearer"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return
    await raw_mcp_app(scope, receive, send)

mcp_app = mcp_auth_app


@asynccontextmanager
async def api_lifespan(app: FastAPI):
    global APP_JOB_WORKER, APP_SHUTTING_DOWN
    ensure_store()
    await asyncio.to_thread(seed_project_knowledge, STORE)
    APP_SHUTTING_DOWN = False
    STORE.recover_stale_jobs(stale_after=90)
    APP_JOB_WORKER = asyncio.create_task(_app_job_worker())
    try:
        async with mcp.session_manager.run():
            yield
    finally:
        APP_SHUTTING_DOWN = True
        if APP_JOB_WORKER:
            APP_JOB_WORKER.cancel()
            await asyncio.gather(APP_JOB_WORKER, return_exceptions=True)
        APP_JOB_WORKER = None
        STORE.close()

api = FastAPI(
    title="Atlas API",
    version="2.0",
    lifespan=api_lifespan,
)

@api.middleware('http')
async def add_security_headers(request: Request, call_next):
    if request.url.path in {'/app-jobs', '/app-task'}:
        raw_length = request.headers.get('content-length')
        try:
            content_length = int(raw_length or '0')
        except ValueError:
            content_length = 0
        if content_length > MAX_APP_BODY_BYTES:
            return Response(
                content='{"detail":"Payload too large"}',
                status_code=413,
                media_type='application/json',
            )
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'camera=(), geolocation=(), microphone=(self)'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response

@api.get("/", include_in_schema=False)
async def atlas_app():
    return FileResponse("web/index.html")


class AppAttachment(BaseModel):
    name: str
    media_type: str
    data: str


class TaskRequest(BaseModel):
    task: str
    previous_response_id: str | None = None
    allow_writes: bool = False
    claude_review: bool = False
    project_id: str = "project-general"
    attachments: list[AppAttachment] = Field(default_factory=list)


class ProjectCreateRequest(BaseModel):
    name: str


class MemoryCreateRequest(BaseModel):
    content: str
    kind: str = "note"


class AppLoginRequest(BaseModel):
    key: str


def app_cookie_valid(request: Request) -> bool:
    return app_session_token_valid(request.cookies.get("atlas_app_session"))


def verify_api_key(x_atlas_key: str | None):
    if not secure_key_match(x_atlas_key, ATLAS_API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )


def verify_bridge_key(x_atlas_key: str | None):
    if not secure_key_match(x_atlas_key, ATLAS_BRIDGE_KEY):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )


def verify_app_key(x_atlas_key: str | None):
    if not secure_key_match(x_atlas_key, ATLAS_APP_KEY):
        raise HTTPException(
            status_code=401,
            detail="Unauthorized",
        )


def verify_app_request(request: Request, x_atlas_key: str | None):
    if app_cookie_valid(request) or secure_key_match(x_atlas_key, ATLAS_APP_KEY):
        return
    raise HTTPException(
        status_code=401,
        detail="Unauthorized",
    )


def verify_user_access(user_id: int | None):
    if not ALLOWED_USER_IDS:
        return True

    if user_id is None:
        return False

    return user_id in ALLOWED_USER_IDS

def validate_app_task_request(body: TaskRequest):
    if len(body.attachments) > APP_ATTACHMENT_MAX_COUNT:
        raise HTTPException(status_code=400, detail='Too many attachments')
    for attachment in body.attachments:
        if len(attachment.data or '') > APP_ATTACHMENT_MAX_DATA_CHARS:
            raise HTTPException(status_code=413, detail='Attachment too large')


def _prune_app_jobs():
    ensure_store()
    STORE.prune_jobs(APP_JOB_RETENTION)


def _public_job(job):
    if not job:
        return None
    return {
        key: job.get(key)
        for key in (
            "job_id",
            "project_id",
            "status",
            "answer",
            "response_id",
            "meta",
            "error",
            "code",
            "created_at",
            "updated_at",
            "started_at",
            "completed_at",
            "retry_count",
        )
    }


async def _run_app_job(job):
    job_id = job["job_id"]
    payload = job.get("payload") or {}
    body = TaskRequest.model_validate(payload)
    current_task = asyncio.current_task()

    async def heartbeat():
        while True:
            await asyncio.sleep(10)
            alive = await asyncio.to_thread(STORE.touch_job, job_id, WORKER_ID)
            if not alive:
                if current_task and not current_task.done():
                    current_task.cancel()
                return

    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        response = await run_atlas(
            body.task,
            body.previous_response_id,
            allow_writes=body.allow_writes,
            attachments=body.attachments,
            claude_review=body.claude_review,
            project_id=body.project_id,
            job_id=job_id,
        )
        if await asyncio.to_thread(STORE.is_cancel_requested, job_id):
            return
        stored = await asyncio.to_thread(
            STORE.finish_job,
            job_id,
            response.output_text,
            response.id,
            {
                "model": response.model,
                "route": response.route,
                "usage": response.usage,
            },
        )
        if stored:
            await asyncio.to_thread(
                STORE.update_project_response,
                body.project_id,
                response.id,
            )
    except asyncio.CancelledError:
        if not APP_SHUTTING_DOWN and not STORE.is_cancel_requested(job_id):
            await asyncio.to_thread(
                STORE.fail_job,
                job_id,
                "Задача была остановлена до завершения.",
                499,
            )
        raise
    except BudgetExceeded as exc:
        await asyncio.to_thread(STORE.fail_job, job_id, str(exc), 429)
    except RateLimitError:
        await asyncio.to_thread(
            STORE.fail_job,
            job_id,
            "Лимит OpenAI временно исчерпан. Попробуйте позже.",
            429,
        )
    except Exception:
        logger.exception("Background app job failed")
        await asyncio.to_thread(
            STORE.fail_job,
            job_id,
            "Сервер Atlas временно недоступен.",
            500,
        )
    finally:
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)


async def _app_job_worker():
    active = set()
    last_recovery = 0.0
    try:
        while True:
            active = {task for task in active if not task.done()}
            now = time.monotonic()
            if now - last_recovery >= 15:
                await asyncio.to_thread(STORE.recover_stale_jobs, 90)
                last_recovery = now
            while len(active) < APP_JOB_MAX_ACTIVE:
                job = await asyncio.to_thread(STORE.claim_next_job, WORKER_ID)
                if not job:
                    break
                task = asyncio.create_task(_run_app_job(job))
                APP_JOB_TASKS[job["job_id"]] = task
                active.add(task)

                def forget(done_task, job_id=job["job_id"]):
                    APP_JOB_TASKS.pop(job_id, None)

                task.add_done_callback(forget)
            await asyncio.sleep(0.5)
    finally:
        for task in active:
            task.cancel()
        if active:
            await asyncio.gather(*active, return_exceptions=True)

@api.get("/health")
async def api_health():
    ensure_store()
    return {
        "ok": True,
        "service": "AtlasCore",
        "process": "alive",
        "config_loaded": True,
        "storage": {
            "backend": STORE.backend,
            "durable": STORE.backend == "postgres",
        },
        "router": MODEL_ROUTER.public_config(),
        "budget": {
            "daily_limit_usd": BUDGET.daily_limit_usd,
            "task_limit_usd": BUDGET.task_limit_usd,
        },
        "jobs": {"max_active": APP_JOB_MAX_ACTIVE},
        "mcp": {
            "enabled": True,
            "endpoint": "/mcp",
        },
        "private": bool(ALLOWED_USER_IDS),
    }

@api.post("/task")
async def api_task(
    body: TaskRequest,
    x_atlas_key: str | None = Header(
        default=None,
        alias="X-Atlas-Key",
    ),
):
    verify_api_key(x_atlas_key)
    validate_app_task_request(body)
    try:
        response = await run_atlas(
            body.task,
            body.previous_response_id,
            allow_writes=body.allow_writes,
            attachments=body.attachments,
            claude_review=body.claude_review,
            project_id=body.project_id,
        )
        STORE.update_project_response(body.project_id, response.id)
        return {
            "ok": True,
            "response_id": response.id,
            "answer": response.output_text,
            "meta": {
                "model": response.model,
                "route": response.route,
                "usage": response.usage,
            },
        }
    except BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except RateLimitError:
        logger.warning("OpenAI rate limit reached")
        raise HTTPException(status_code=429, detail="OpenAI API rate limit reached.")
    except Exception:
        logger.exception("API task failed")
        raise HTTPException(status_code=500, detail="Internal server error")

@api.post("/app-login")
async def app_login(body: AppLoginRequest, response: Response):
    if not secure_key_match(body.key, ATLAS_APP_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")

    response.set_cookie(
        "atlas_app_session",
        app_session_token(),
        httponly=True,
        secure=True,
        samesite="strict",
        max_age=APP_SESSION_MAX_AGE,
        path="/",
    )
    return {"ok": True}


@api.get("/app-session")
async def app_session(request: Request):
    return {"authenticated": app_cookie_valid(request)}


@api.post("/app-logout")
async def app_logout(response: Response):
    response.delete_cookie('atlas_app_session', path='/')
    return {"ok": True}


@api.post("/app-jobs")
async def api_app_jobs(
    body: TaskRequest,
    request: Request,
    x_atlas_key: str | None = Header(
        default=None,
        alias="X-Atlas-Key",
    ),
):
    verify_app_request(request, x_atlas_key)
    _prune_app_jobs()
    validate_app_task_request(body)
    try:
        job = await asyncio.to_thread(
            STORE.create_job,
            body.model_dump(mode="json"),
        )
    except TooManyJobs:
        raise HTTPException(
            status_code=409,
            detail="Слишком много активных задач. Дождитесь завершения текущих задач.",
        )
    return {"ok": True, "job_id": job["job_id"], "status": job["status"]}


@api.get("/app-jobs/{job_id}")
async def api_app_job_get(
    job_id: str,
    request: Request,
    x_atlas_key: str | None = Header(
        default=None,
        alias="X-Atlas-Key",
    ),
):
    verify_app_request(request, x_atlas_key)
    _prune_app_jobs()
    job = await asyncio.to_thread(STORE.get_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, **_public_job(job)}


@api.delete("/app-jobs/{job_id}")
async def api_app_job_delete(
    job_id: str,
    request: Request,
    x_atlas_key: str | None = Header(
        default=None,
        alias="X-Atlas-Key",
    ),
):
    verify_app_request(request, x_atlas_key)
    _prune_app_jobs()
    job = await asyncio.to_thread(STORE.cancel_job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    task = APP_JOB_TASKS.get(job_id)
    if task and not task.done():
        task.cancel()
    return {"ok": True, **_public_job(job)}


@api.post("/app-task")
async def api_app_task(
    body: TaskRequest,
    request: Request,
    x_atlas_key: str | None = Header(
        default=None,
        alias="X-Atlas-Key",
    ),
):
    verify_app_request(request, x_atlas_key)
    validate_app_task_request(body)
    try:
        response = await run_atlas(
            body.task,
            body.previous_response_id,
            allow_writes=body.allow_writes,
            attachments=body.attachments,
            claude_review=body.claude_review,
            project_id=body.project_id,
        )
        STORE.update_project_response(body.project_id, response.id)
        return {
            "ok": True,
            "response_id": response.id,
            "answer": response.output_text,
            "meta": {
                "model": response.model,
                "route": response.route,
                "usage": response.usage,
            },
        }
    except BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))
    except RateLimitError:
        logger.warning("OpenAI rate limit reached")
        raise HTTPException(status_code=429, detail="OpenAI API rate limit reached.")
    except Exception:
        logger.exception("App task failed")
        raise HTTPException(status_code=500, detail="Internal server error")


@api.get("/app-projects")
async def api_projects(
    request: Request,
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    ensure_store()
    return {"ok": True, "projects": await asyncio.to_thread(STORE.list_projects)}


@api.post("/app-projects")
async def api_project_create(
    body: ProjectCreateRequest,
    request: Request,
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    try:
        project = await asyncio.to_thread(STORE.create_project, body.name)
    except AtlasStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "project": project}


@api.get("/app-projects/{project_id}/memory")
async def api_project_memory(
    project_id: str,
    request: Request,
    q: str = "",
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    memories = await asyncio.to_thread(STORE.search_memories, project_id, q, 30)
    return {"ok": True, "project_id": project_id, "memories": memories}


@api.post("/app-projects/{project_id}/memory")
async def api_project_memory_create(
    project_id: str,
    body: MemoryCreateRequest,
    request: Request,
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    try:
        memory = await asyncio.to_thread(
            STORE.remember,
            project_id,
            body.content,
            body.kind,
        )
    except AtlasStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "memory": memory}


@api.delete("/app-projects/{project_id}/memory/{memory_id}")
async def api_project_memory_delete(
    project_id: str,
    memory_id: str,
    request: Request,
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    deleted = await asyncio.to_thread(STORE.delete_memory, project_id, memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return {"ok": True, "deleted": True}


@api.get("/app-projects/{project_id}/history")
async def api_project_history(
    project_id: str,
    request: Request,
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    jobs = await asyncio.to_thread(STORE.list_recent_jobs, project_id, 50)
    history = []
    for job in jobs:
        payload = job.get("payload") or {}
        history.append(
            {
                "job_id": job.get("job_id"),
                "task": payload.get("task", ""),
                "allow_writes": bool(payload.get("allow_writes")),
                "status": job.get("status"),
                "answer": job.get("answer", ""),
                "response_id": job.get("response_id"),
                "created_at": job.get("created_at"),
                "completed_at": job.get("completed_at"),
                "meta": job.get("meta", {}),
            }
        )
    return {"ok": True, "project_id": project_id, "history": history}


@api.get("/app-actions")
async def api_actions(
    request: Request,
    project_id: str = "project-general",
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    actions = await asyncio.to_thread(STORE.list_actions, project_id, 100)
    return {"ok": True, "project_id": project_id, "actions": actions}


@api.get("/app-plugins")
async def api_plugins(
    request: Request,
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    return {"ok": True, "plugins": plugin_registry()}


@api.get("/app-system-status")
async def api_system_status(
    request: Request,
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    systems = system_registry(STORE.backend)
    issues = [
        {"id": item["id"], "name": item["name"], "status": item["status"]}
        for item in systems
        if item["id"] in {"openai", "github", "postgres"} and not item["connected"]
    ]
    return {
        "ok": not issues,
        "storage_backend": STORE.backend,
        "systems": systems,
        "issues": issues,
        "checked_at": int(time.time()),
    }


@api.get("/app-permissions")
async def api_permissions(
    request: Request,
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    return {"ok": True, "levels": PERMISSION_LEVELS}


@api.get("/app-budget")
async def api_budget(
    request: Request,
    x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
):
    verify_app_request(request, x_atlas_key)
    return {"ok": True, **await asyncio.to_thread(BUDGET.status)}

@api.post("/bridge")
async def api_bridge(
    request: Request,
    x_atlas_key: str | None = Header(
        default=None,
        alias="X-Atlas-Key",
    ),
):
    verify_bridge_key(x_atlas_key)

    try:
        task = (await request.body()).decode("utf-8").strip()

        if not task:
            raise HTTPException(
                status_code=400,
                detail="Empty task",
            )

        response = await run_atlas(task)
        answer = (response.output_text or "").strip()

        return {
            "ok": True,
            "response_id": response.id,
            "answer": answer,
        }

    except HTTPException:
        raise

    except BudgetExceeded as exc:
        raise HTTPException(status_code=429, detail=str(exc))

    except RateLimitError:
        logger.warning("OpenAI rate limit reached")

        raise HTTPException(
            status_code=429,
            detail="OpenAI API rate limit reached.",
        )

    except Exception:
        logger.exception("Bridge task failed")

        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


# MCP Streamable HTTP endpoint:
# https://YOUR-RAILWAY-DOMAIN/mcp
api.mount("/mcp", mcp_app)
api.mount("/app", StaticFiles(directory="web", html=True), name="app")


# ---------------- TELEGRAM ----------------

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user_id = (
        update.effective_user.id
        if update.effective_user
        else None
    )

    if not verify_user_access(user_id):
        return

    await update.message.reply_text(
        "ATLAS ONLINE â\n\n"
        "Telegram: â\n"
        "API: â\n"
        "MCP bridge: â\n"
        "OpenAI: â\n"
        "GitHub READ: â\n"
        "GitHub WRITE: â"
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

    if not verify_user_access(user_id):
        return

    railway = os.environ.get(
        "RAILWAY_ENVIRONMENT_NAME",
        "unknown",
    )

    await update.message.reply_text(
        "ATLAS STATUS â\n\n"
        "Telegram: â online\n"
        f"Railway: {railway}\n"
        "API: â\n"
        "MCP bridge: â /mcp\n"
        "OpenAI: â\n"
        "GitHub READ: â\n"
        "GitHub WRITE: â\n"
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

    if not verify_user_access(user_id):
        return

    url = f"https://api.github.com/repos/{REPO}"

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            url,
            headers=github_headers(),
        )

    if response.status_code != 200:
        await update.message.reply_text(
            f"GitHub error: {response.status_code}"
        )
        return

    data = response.json()

    await update.message.reply_text(
        "GitHub Ð¿Ð¾Ð´ÐºÐ»ÑÑÑÐ½ â\n\n"
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

    if not verify_user_access(user_id):
        return

    await update.message.reply_text(
        "Telegram Atlas ÑÐ°Ð±Ð¾ÑÐ°ÐµÑ Ð±ÐµÐ· Ð½Ð°ÐºÐ¾Ð¿Ð»ÐµÐ½Ð¸Ñ Ð¸ÑÑÐ¾ÑÐ¸Ð¸ â"
    )


async def message_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.message.text:
        return

    user_id = (
        update.effective_user.id
        if update.effective_user
        else None
    )

    if not verify_user_access(user_id):
        return

    await update.message.chat.send_action(
        ChatAction.TYPING
    )

    try:
        response = await run_atlas(
            update.message.text
        )

        text = (response.output_text or "").strip()

        if not text:
            text = (
                "Atlas Ð²ÑÐ¿Ð¾Ð»Ð½Ð¸Ð» Ð·Ð°Ð¿ÑÐ¾Ñ, Ð½Ð¾ Ð¸ÑÐ¾Ð³Ð¾Ð²ÑÐ¹ ÑÐµÐºÑÑ "
                "Ð¾ÐºÐ°Ð·Ð°Ð»ÑÑ Ð¿ÑÑÑÑÐ¼."
            )

        await update.message.reply_text(
            text[:4000]
        )

    except RateLimitError:
        logger.warning("Telegram OpenAI rate limit")

        await update.message.reply_text(
            "Лимит OpenAI API временно достигнут."
        )

    except Exception:
        logger.exception("Telegram Atlas error")

        await update.message.reply_text(
            "Atlas error\n"
            "Внутренняя ошибка. Попробуйте еще раз."
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
    logger.info("ATLAS CORE ONLINE")

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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("repo", repo))
    app.add_handler(CommandHandler("reset", reset))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            message_handler,
        )
    )

    app.add_error_handler(error_handler)
    app.run_polling()


if __name__ == "__main__":
    main()