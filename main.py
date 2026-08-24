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
MAX_TOOL_CYCLES = 4
MAX_USER_INPUT_CHARS = 6000
MAX_GITHUB_READ_CHARS = 8000
MAX_GITHUB_READ_LINES = 250
MAX_TELEGRAM_REPLY_CHARS = 4000

ALLOWED_USER_IDS = {
    int(x)
    for x in os.environ.get("ALLOWED_USER_IDS", "").split(",")
    if x.strip()
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger("atlas")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
Ты Atlas — персональный ИИ-ассистент и ядро автоматизации.

У тебя есть реальные инструменты GitHub для репозитория AtlasCore.

У тебя есть инструменты:
- github_list_files — показать файлы и папки;
- github_read_file — читать файлы по нужным кускам;
- github_write_file — создавать или полностью обновлять файлы;
- github_replace_text — точечно менять небольшой фрагмент, если old_text встречается ровно один раз;
- GitHub commit.

Обычные вопросы решай без GitHub.
Файлы читай только нужными кусками.
Небольшие изменения делай через github_replace_text.

Если пользователь спрашивает о репозитории или коде и нужны файлы, используй GitHub-инструменты.
Если пользователь просит создать или изменить файл, используй подходящий GitHub-инструмент.

Никогда не говори, что действие выполнено, если инструмент вернул ошибку.
При изменении main.py сначала прочитай текущий файл.
Отвечай на языке пользователя.
""".strip()

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
                "path": {"type": "string"},
                "start_line": {"type": "integer", "minimum": 1},
                "end_line": {"type": "integer", "minimum": 1},
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
        "name": "github_replace_text",
        "description": "Серверно прочитать файл, заменить ровно один фрагмент old_text на new_text и сделать commit",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string"},
                "new_text": {"type": "string"},
                "commit_message": {"type": "string"},
            },
            "required": ["path", "old_text", "new_text", "commit_message"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def github_headers():
    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def clamp_text(text: str, limit: int) -> str:
    return text[:limit] if len(text) > limit else text


async def github_list_files(path=""):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=github_headers())
    if response.status_code != 200:
        return json.dumps({"ok": False, "status": response.status_code, "error": response.text[:500]}, ensure_ascii=False)
    data = response.json()
    items = [{"name": item.get("name"), "path": item.get("path"), "type": item.get("type")} for item in data] if isinstance(data, list) else [{"name": data.get("name"), "path": data.get("path"), "type": data.get("type")}]
    return json.dumps({"ok": True, "items": items}, ensure_ascii=False)


async def github_read_file(path, start_line=None, end_line=None):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=github_headers())
    if response.status_code != 200:
        return json.dumps({"ok": False, "status": response.status_code, "path": path}, ensure_ascii=False)
    data = response.json()
    if data.get("type") != "file":
        return json.dumps({"ok": False, "error": "not_a_file"}, ensure_ascii=False)
    try:
        content = base64.b64decode(data["content"]).decode("utf-8")
    except Exception as exc:
        return json.dumps({"ok": False, "error": "decode_failed", "details": str(exc)}, ensure_ascii=False)
    lines = content.splitlines()
    total_lines = len(lines)
    s = max(1, int(start_line) if start_line is not None else 1)
    e = int(end_line) if end_line is not None else min(total_lines, s + MAX_GITHUB_READ_LINES - 1)
    if e < s:
        e = s
    e = min(e, s + MAX_GITHUB_READ_LINES - 1, total_lines)
    chunk = "\n".join(lines[s - 1:e])
    return json.dumps({"ok": True, "path": path, "sha": data.get("sha"), "start_line": s, "end_line": e, "total_lines": total_lines, "content": clamp_text(chunk, MAX_GITHUB_READ_CHARS)}, ensure_ascii=False)


async def github_write_file(path, content, commit_message):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    payload = {"message": commit_message, "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"), "branch": "main"}
    async with httpx.AsyncClient(timeout=30) as client:
        current = await client.get(url, headers=github_headers())
        if current.status_code == 200:
            payload["sha"] = current.json()["sha"]
        elif current.status_code != 404:
            return json.dumps({"ok": False, "status": current.status_code, "step": "read_existing"}, ensure_ascii=False)
        response = await client.put(url, headers=github_headers(), json=payload)
    if response.status_code not in (200, 201):
        return json.dumps({"ok": False, "status": response.status_code, "step": "write", "error": response.text[:1000]}, ensure_ascii=False)
    data = response.json()
    return json.dumps({"ok": True, "path": path, "commit_sha": data.get("commit", {}).get("sha"), "file_url": data.get("content", {}).get("html_url")}, ensure_ascii=False)


async def github_replace_text(path, old_text, new_text, commit_message):
    url = f"https://api.github.com/repos/{REPO}/contents/{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        current = await client.get(url, headers=github_headers())
        if current.status_code != 200:
            return json.dumps({"ok": False, "status": current.status_code, "step": "read_existing"}, ensure_ascii=False)
        data = current.json()
        try:
            content = base64.b64decode(data["content"]).decode("utf-8")
        except Exception as exc:
            return json.dumps({"ok": False, "error": "decode_failed", "details": str(exc)}, ensure_ascii=False)
        count = content.count(old_text)
        if count != 1:
            return json.dumps({"ok": False, "error": "old_text_must_appear_exactly_once", "matches": count}, ensure_ascii=False)
        updated = content.replace(old_text, new_text, 1)
        payload = {"message": commit_message, "content": base64.b64encode(updated.encode("utf-8")).decode("utf-8"), "branch": "main", "sha": data["sha"]}
        response = await client.put(url, headers=github_headers(), json=payload)
    if response.status_code not in (200, 201):
        return json.dumps({"ok": False, "status": response.status_code, "step": "write", "error": response.text[:1000]}, ensure_ascii=False)
    resp = response.json()
    return json.dumps({"ok": True, "path": path, "commit_sha": resp.get("commit", {}).get("sha"), "file_url": resp.get("content", {}).get("html_url")}, ensure_ascii=False)


async def execute_tool(name, arguments):
    if name == "github_list_files":
        return await github_list_files(arguments.get("path", ""))
    if name == "github_read_file":
        return await github_read_file(arguments["path"], arguments.get("start_line"), arguments.get("end_line"))
    if name == "github_write_file":
        return await github_write_file(arguments["path"], arguments["content"], arguments["commit_message"])
    if name == "github_replace_text":
        return await github_replace_text(arguments["path"], arguments["old_text"], arguments["new_text"], arguments["commit_message"])
    return json.dumps({"ok": False, "error": "unknown_tool"}, ensure_ascii=False)


def create_response(**kwargs):
    kwargs.setdefault("max_output_tokens", 1200)
    return openai_client.responses.create(**kwargs)


async def run_atlas(text, previous_response_id=None):
    text = clamp_text(text, MAX_USER_INPUT_CHARS)
    request = {"model": MODEL, "instructions": SYSTEM_PROMPT, "input": text, "tools": TOOLS, "tool_choice": "auto", "max_output_tokens": 1200}
    if previous_response_id:
        request["previous_response_id"] = previous_response_id
    response = await asyncio.to_thread(create_response, **request)
    for _ in range(MAX_TOOL_CYCLES):
        tool_calls = [item for item in response.output if getattr(item, "type", None) == "function_call"]
        if not tool_calls:
            return response
        outputs = []
        for call in tool_calls:
            try:
                arguments = json.loads(call.arguments)
                result = await execute_tool(call.name, arguments)
            except Exception as exc:
                logger.exception("Tool execution failed")
                result = json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
            outputs.append({"type": "function_call_output", "call_id": call.call_id, "output": result})
        response = await asyncio.to_thread(create_response, model=MODEL, instructions=SYSTEM_PROMPT, previous_response_id=response.id, input=outputs, tools=TOOLS, tool_choice="auto", max_output_tokens=1200)
    return response


api = FastAPI(title="Atlas API", version="1.0")


class TaskRequest(BaseModel):
    task: str
    previous_response_id: str | None = None


def verify_api_key(x_atlas_key: str | None):
    if x_atlas_key != ATLAS_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def verify_user_access(user_id: int | None):
    if ALLOWED_USER_IDS and (user_id is None or user_id not in ALLOWED_USER_IDS):
        return False
    return True


@api.get("/health")
async def api_health():
    return {"ok": True, "service": "AtlasCore", "telegram": True, "openai": True, "github": True, "private": bool(ALLOWED_USER_IDS)}


@api.post("/task")
async def api_task(body: TaskRequest, x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key")):
    verify_api_key(x_atlas_key)
    try:
        response = await run_atlas(body.task, body.previous_response_id)
        return {"ok": True, "response_id": response.id, "answer": response.output_text}
    except RateLimitError:
        raise HTTPException(status_code=429, detail="Лимит OpenAI API временно достигнут. Попробуй позже — Atlas не сломан")
    except Exception as exc:
        logger.exception("API task failed")
        raise HTTPException(status_code=500, detail=str(exc))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verify_user_access(update.effective_user.id if update.effective_user else None):
        return
    await update.message.reply_text("ATLAS ONLINE ✅\n\nTelegram: ✅\nAPI: ✅\nOpenAI: ✅\nGitHub READ: ✅\nGitHub WRITE: ✅")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verify_user_access(update.effective_user.id if update.effective_user else None):
        return
    railway = os.environ.get("RAILWAY_ENVIRONMENT_NAME", "unknown")
    await update.message.reply_text(f"ATLAS STATUS ✅\n\nTelegram: ✅ online\nRailway: {railway}\nAPI: ✅\nOpenAI: ✅\nGitHub READ: ✅\nGitHub WRITE: ✅\nRepo: {REPO}\nModel: {MODEL}")


async def repo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verify_user_access(update.effective_user.id if update.effective_user else None):
        return
    url = f"https://api.github.com/repos/{REPO}"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(url, headers=github_headers())
    if response.status_code != 200:
        await update.message.reply_text(f"GitHub error: {response.status_code}")
        return
    data = response.json()
    await update.message.reply_text(f"GitHub подключён ✅\n\nRepo: {data.get('full_name')}\nBranch: {data.get('default_branch')}\nVisibility: {data.get('visibility')}")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not verify_user_access(update.effective_user.id if update.effective_user else None):
        return
    context.user_data.pop("previous_response_id", None)
    await update.message.reply_text("Память диалога очищена ✅")


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if not verify_user_access(update.effective_user.id if update.effective_user else None):
        return
    await update.message.chat.send_action(ChatAction.TYPING)
    try:
        response = await run_atlas(clamp_text(update.message.text, MAX_USER_INPUT_CHARS), None)
        text = response.output_text.strip() or "Atlas выполнил запрос, но не вернул текстовый ответ."
        await update.message.reply_text(clamp_text(text, MAX_TELEGRAM_REPLY_CHARS))
    except RateLimitError:
        await update.message.reply_text("Лимит OpenAI API временно достигнут. Попробуй позже — Atlas не сломан")
    except Exception as exc:
        logger.exception("Telegram Atlas error")
        await update.message.reply_text(f"Atlas error ❌\n{type(exc).__name__}: {exc}")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.exception("Telegram error", exc_info=context.error)


def run_api():
    uvicorn.run(api, host="0.0.0.0", port=PORT, log_level="info")


def main():
    logger.info("ATLAS API CORE ONLINE")
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("repo", repo))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    app.add_error_handler(error_handler)
    app.run_polling()


if __name__ == "__main__":
    main()
