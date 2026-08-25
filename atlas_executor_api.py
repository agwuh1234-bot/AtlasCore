from __future__ import annotations

import secrets
from typing import Callable

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from atlas_claude_bridge import ClaudeBridge


class ClaudeExecutorRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    system: str | None = Field(default=None, max_length=20_000)


def build_executor_router(*, bridge_key: str, claude: ClaudeBridge | None = None) -> APIRouter:
    """Create authenticated executor endpoints without exposing provider secrets."""
    router = APIRouter(prefix="/executor", tags=["executor"])
    claude_bridge = claude or ClaudeBridge()

    def authorize(provided: str | None) -> None:
        if not provided or not secrets.compare_digest(provided, bridge_key):
            raise HTTPException(status_code=401, detail="Unauthorized")

    @router.get("/capabilities")
    async def capabilities(
        x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key"),
    ):
        authorize(x_atlas_bridge_key)
        return {
            "ok": True,
            "capabilities": {
                "claude": {
                    "configured": claude_bridge.configured,
                    "model": claude_bridge.model if claude_bridge.configured else None,
                    "actions": ["ask", "code", "review", "reason"],
                }
            },
        }

    @router.post("/claude")
    async def claude_execute(
        body: ClaudeExecutorRequest,
        x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key"),
    ):
        authorize(x_atlas_bridge_key)
        result = await claude_bridge.ask(body.prompt, system=body.system)
        if not result.get("ok"):
            status = 502 if result.get("error") != "claude_not_configured" else 503
            raise HTTPException(status_code=status, detail=result)
        return result

    return router
