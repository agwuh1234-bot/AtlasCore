from __future__ import annotations

import json
import secrets

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from atlas_n8n import N8NBridgeError, call_tool, configured, list_tools
from atlas_n8n_policy import decision, preflight


class N8NPreflightRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    intent: str = Field(pattern="^(read|write)$")


class N8NCallRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    intent: str = Field(pattern="^(read|write)$")
    arguments: dict = Field(default_factory=dict)


def _authorize(provided: str | None, expected: str) -> None:
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


def _result_payload(result) -> dict:
    payload = {
        "ok": not bool(getattr(result, "isError", False)),
        "is_error": bool(getattr(result, "isError", False)),
    }
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        payload["structured_content"] = structured
    content = []
    for block in getattr(result, "content", []) or []:
        if hasattr(block, "text"):
            text = block.text
            try:
                content.append({"type": "json", "value": json.loads(text)})
            except Exception:
                content.append({"type": "text", "text": text})
        else:
            content.append({"type": type(block).__name__, "value": str(block)})
    payload["content"] = content
    return payload


def build_n8n_executor_router(*, bridge_key: str) -> APIRouter:
    router = APIRouter(prefix="/executor/n8n", tags=["executor", "n8n"])

    @router.get("/tools")
    async def tools(
        x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key"),
    ):
        _authorize(x_atlas_bridge_key, bridge_key)
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
    ):
        _authorize(x_atlas_bridge_key, bridge_key)
        if not configured():
            raise HTTPException(status_code=503, detail="n8n_not_configured")
        discovered = await list_tools()
        return preflight(discovered, body.name, body.intent)

    @router.post("/call")
    async def tool_call(
        body: N8NCallRequest,
        x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key"),
    ):
        _authorize(x_atlas_bridge_key, bridge_key)
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
