import os
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

import httpx
import uvicorn

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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
MODEL = "gpt-5.4-mini"
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
APP_JOBS = {}
APP_JOB_TASKS = {}
APP_JOB_TTL = 3600
APP_SESSION_MAX_AGE = 30 * 24 * 3600


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
import os
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

import httpx
import uvicorn

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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
MODEL = "gpt-5.4-mini"
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
APP_JOBS = {}
APP_JOB_TASKS = {}
APP_JOB_TTL = 3600
APP_SESSION_MAX_AGE = 30 * 24 * 3600


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
Ты Atlas — персональный ИИ-ассистент и ядро автоматизации.

У тебя есть реальные GitHub-инструменты для AtlasCore.

Главные правила:
- обычные вопросы решай без GitHub;
- не читай файлы без необходимости;
- большие файлы читай только нужными диапазонами строк;
- небольшие изменения делай точечно;
- не делай лишних повторных вызовов инструментов;
- если пользователь просит проверить реальный код или репозиторий,
  используй GitHub-инструменты;
- никогда не утверждай, что действие выполнено, если инструмент вернул ошибку;
- при работе с main.py не удаляй рабочие функции без необходимости;
- после использования инструментов обязательно верни пользователю
  нормальный текстовый итог.
- Use claude_ask for a useful second opinion on complex coding, architecture, debugging, or reasoning. Do not call Claude for simple requests.

Отвечай кратко и на языке пользователя.
"""

SYSTEM_PROMPT = """Ты Atlas — персональный ИИ-ассистент и оркестратор.
Отвечай на языке пользователя.
Используй web_search для свежей публичной информации.
Используй claude_ask, когда пользователь прямо просит спросить Claude или когда независимое второе мнение заметно улучшит сложный анализ. Не вызывай Claude для простых запросов.
GitHub read tools для чтения; github_replace_text/github_write_file изменяют репозиторий и могут отсутствовать без разрешения записи; если их нет — попроси включить разрешение изменений.
Не утверждай успех при ошибке инструмента.
После инструментов всегда верни краткий понятный итог."""

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