import os
import secrets
import json
import logging
import asyncio
import base64
import threading
from contextlib import asynccontextmanager

import httpx
import uvicorn

from fastapi import FastAPI, Header, HTTPException, Request
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


for _env_name in ("BOT_TOKEN", "OPENAI_API_KEY", "GITHUB_TOKEN", "ATLAS_API_KEY", "ATLAS_BRIDGE_KEY"):
    if not os.environ.get(_env_name):
        raise RuntimeError(f"Missing required env: {_env_name}")

BOT_TOKEN = os.environ["BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
ATLAS_API_KEY = os.environ["ATLAS_API_KEY"]
ATLAS_BRIDGE_KEY = os.environ["ATLAS_BRIDGE_KEY"]
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


def secure_key_match(provided: str | None, expected: str) -> bool:
    return bool(provided) and secrets.compare_digest(provided, expected)


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

ÐÑÐ²ÐµÑÐ°Ð¹ ÐºÑÐ°ÑÐºÐ¾ Ð¸ Ð½Ð° ÑÐ·ÑÐºÐµ Ð¿Ð¾Ð»ÑÐ·Ð¾Ð²Ð°ÑÐµÐ»Ñ.
"""


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


async def execute_tool(name, arguments):
    if name == "github_list_files":
        return await github_list_files(arguments.get("path", ""))

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
    kwargs.setdefault("max_output_tokens", MAX_OUTPUT_TOKENS)
    return openai_client.responses.create(**kwargs)


async def run_atlas(text, previous_response_id=None):
    text = (text or "")[:MAX_USER_INPUT]

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

    for loop_index in range(MAX_TOOL_LOOPS):
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
            model=MODEL,
            instructions=SYSTEM_PROMPT,
            previous_response_id=response.id,
            input=outputs,
            tools=TOOLS,
            tool_choice="none" if last_loop else "auto",
        )

    return response


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
    async with mcp.session_manager.run():
        yield


api = FastAPI(
    title="Atlas API",
    version="2.0",
    lifespan=api_lifespan,
)


@api.get("/", include_in_schema=False)
async def atlas_app():
    return FileResponse("web/index.html")


class TaskRequest(BaseModel):
    task: str
    previous_response_id: str | None = None


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


def verify_user_access(user_id: int | None):
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
        "process": "alive",
        "config_loaded": True,
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

    try:
        response = await run_atlas(
            body.task,
            body.previous_response_id,
        )

        answer = (response.output_text or "").strip()

        return {
            "ok": True,
            "response_id": response.id,
            "answer": answer,
        }

    except RateLimitError:
        logger.warning("OpenAI rate limit reached")

        raise HTTPException(
            status_code=429,
            detail="OpenAI API rate limit reached.",
        )

    except Exception:
        logger.exception("API task failed")

        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


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