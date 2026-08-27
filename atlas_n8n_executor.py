from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from atlas_n8n import N8NBridgeError, call_tool, configured, list_tools
from atlas_n8n_policy import decision, preflight
from atlas_safe_logging import sanitize_for_log


class N8NPreflightRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    intent: str = Field(pattern="^(read|write)$")


class N8NCallRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    intent: str = Field(pattern="^(read|write)$")
    arguments: dict = Field(default_factory=dict)


_SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
    "credential",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
)
_MAX_TEXT_RESULT = 4000
_MAX_REDACTION_DEPTH = 12


def _authorized(provided: str | None, expected: str | None) -> bool:
    return bool(provided and expected and secrets.compare_digest(provided, expected))


def _authorize(
    atlas_key: str | None,
    chatgpt_key: str | None,
    *,
    bridge_key: str,
    chatgpt_bridge_key: str | None,
) -> None:
    if _authorized(atlas_key, bridge_key):
        return
    if _authorized(chatgpt_key, chatgpt_bridge_key):
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


def _looks_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return any(fragment in normalized for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _redact_result(value, *, depth: int = 0):
    if depth >= _MAX_REDACTION_DEPTH:
        return "[REDACTED_DEPTH_LIMIT]"
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if _looks_sensitive_key(key) else _redact_result(child, depth=depth + 1)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [_redact_result(child, depth=depth + 1) for child in value]
    if isinstance(value, tuple):
        return [_redact_result(child, depth=depth + 1) for child in value]
    return value


def _bounded_text(text: object) -> str:
    sanitized = sanitize_for_log(str(text))
    value = sanitized if isinstance(sanitized, str) else str(sanitized)
    if len(value) <= _MAX_TEXT_RESULT:
        return value
    return value[:_MAX_TEXT_RESULT] + "...[TRUNCATED]"


def _result_payload(result) -> dict:
    payload = {
        "ok": not bool(getattr(result, "isError", False)),
        "is_error": bool(getattr(result, "isError", False)),
    }
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        payload["structured_content"] = _redact_result(structured)
    content = []
    for block in getattr(result, "content", []) or []:
        if hasattr(block, "text"):
            text = block.text
            try:
                content.append({"type": "json", "value": _redact_result(json.loads(text))})
            except Exception:
                content.append({"type": "text", "text": _bounded_text(text)})
        else:
            content.append({"type": type(block).__name__, "value": _bounded_text(block)})
    payload["content"] = content
    return payload


def build_n8n_executor_router(*, bridge_key: str, chatgpt_bridge_key: str | None = None) -> APIRouter:
    router = APIRouter(prefix="/executor/n8n", tags=["executor", "n8n"])

    def authorize_headers(atlas_key: str | None, chatgpt_key: str | None) -> None:
        _authorize(
            atlas_key,
            chatgpt_key,
            bridge_key=bridge_key,
            chatgpt_bridge_key=chatgpt_bridge_key,
        )

    @router.get("/tools")
    async def tools(
        x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key"),
        x_chatgpt_bridge_key: str | None = Header(default=None, alias="X-ChatGPT-Bridge-Key"),
    ):
        authorize_headers(x_atlas_bridge_key, x_chatgpt_bridge_key)
        if not configured():
            raise HTTPException(status_code=503, detail="n8n_not_configured")
        try:
            discovered = await list_tools()
            return {"ok": True, "count": len(discovered), "tools": discovered}
        except N8NBridgeError as exc:
            raise HTTPException(status_code=502, detail={"error": "n8n_bridge_error", "detail": str(exc)})

    @router.post("/preflight")
    async def tool_preflight(
        body: N8NPreflightRequest,
        x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key"),
        x_chatgpt_bridge_key: str | None = Header(default=None, alias="X-ChatGPT-Bridge-Key"),
    ):
        authorize_headers(x_atlas_bridge_key, x_chatgpt_bridge_key)
        if not configured():
            raise HTTPException(status_code=503, detail="n8n_not_configured")
        discovered = await list_tools()
        return preflight(discovered, body.name, body.intent)

    @router.post("/call")
    async def tool_call(
        body: N8NCallRequest,
        x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key"),
        x_chatgpt_bridge_key: str | None = Header(default=None, alias="X-ChatGPT-Bridge-Key"),
    ):
        authorize_headers(x_atlas_bridge_key, x_chatgpt_bridge_key)
        if not configured():
            raise HTTPException(status_code=503, detail="n8n_not_configured")

        discovered = await list_tools()
        check = preflight(discovered, body.name, body.intent)
        if not check.get("found"):
            raise HTTPException(status_code=404, detail=check)
        if not check.get("allowed"):
            raise HTTPException(status_code=403, detail=check)

        allowed, reason = decision(body.name, body.intent)
        if not allowed:
            raise HTTPException(status_code=403, detail={"error": "n8n_policy_blocked", "reason": reason})

        try:
            result = await call_tool(body.name, body.arguments)
            return _result_payload(result)
        except N8NBridgeError as exc:
            raise HTTPException(status_code=502, detail={"error": "n8n_bridge_error", "detail": str(exc)})

    return router
