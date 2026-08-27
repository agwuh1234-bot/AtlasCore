"""Minimal authenticated browser error telemetry for Atlas UI diagnostics."""

import json
import logging
from typing import Any, Callable

from fastapi import APIRouter, Request

logger = logging.getLogger("atlas.client")


def _text(value: Any, limit: int) -> str:
    if value is None:
        return ""
    return str(value).replace("\x00", "")[:limit]


def build_client_error_router(*, verify_request: Callable) -> APIRouter:
    router = APIRouter(prefix="/app-client-error", tags=["atlas-client-error"])

    @router.post("")
    async def capture_client_error(request: Request):
        verify_request(request, None)
        try:
            body = await request.json()
        except Exception:
            body = {}
        safe = {
            "kind": _text(body.get("kind"), 40),
            "message": _text(body.get("message"), 500),
            "source": _text(body.get("source"), 300),
            "line": _text(body.get("line"), 20),
            "column": _text(body.get("column"), 20),
            "stack": _text(body.get("stack"), 1200),
            "path": _text(body.get("path"), 300),
            "ua": _text(body.get("ua"), 400),
            "ready": _text(body.get("ready"), 40),
        }
        logger.error("CLIENT_UI_ERROR %s", json.dumps(safe, ensure_ascii=False, separators=(",", ":")))
        return {"ok": True}

    return router
