"""Safe, authenticated integration status metadata for the Atlas UI.

Only booleans and non-secret runtime labels are exposed. Provider tokens,
credential IDs, URLs containing secrets, and environment values stay private.
"""

from __future__ import annotations

import os
from typing import Callable

from fastapi import APIRouter, Header, Request

from atlas_claude_bridge import ClaudeBridge
from atlas_n8n import configured as n8n_configured


DEFAULT_REPO = "agwuh1234-bot/AtlasCore"


def _present(name: str) -> bool:
    return bool(str(os.environ.get(name, "")).strip())


def _railway_runtime() -> dict:
    running = any(
        _present(name)
        for name in (
            "RAILWAY_PROJECT_ID",
            "RAILWAY_ENVIRONMENT_ID",
            "RAILWAY_SERVICE_ID",
            "RAILWAY_STATIC_URL",
        )
    )
    service = str(os.environ.get("RAILWAY_SERVICE_NAME", "")).strip()[:120] or None
    environment = str(os.environ.get("RAILWAY_ENVIRONMENT_NAME", "")).strip()[:120] or None
    return {"running": running, "service": service, "environment": environment}


def _shopify_direct_configured() -> bool:
    # Do not return which secret variables exist; only a coarse capability flag.
    secret_markers = (
        "SHOPIFY_ACCESS_TOKEN",
        "SHOPIFY_ADMIN_API_TOKEN",
        "SHOPIFY_API_KEY",
        "SHOPIFY_STORE_DOMAIN",
    )
    return any(_present(name) for name in secret_markers)


def build_integrations_status_router(*, verify_request: Callable) -> APIRouter:
    router = APIRouter(prefix="/app-integrations", tags=["app", "integrations"])

    @router.get("/status")
    async def status(
        request: Request,
        x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
    ):
        verify_request(request, x_atlas_key)
        claude = ClaudeBridge()
        return {
            "ok": True,
            "atlas": {"online": True},
            "github": {
                "configured": _present("GITHUB_TOKEN"),
                "repository": str(os.environ.get("GITHUB_REPO", DEFAULT_REPO)).strip()[:240]
                or DEFAULT_REPO,
            },
            "n8n": {"configured": n8n_configured()},
            "shopify": {
                "studio_available": True,
                "direct_configured": _shopify_direct_configured(),
                "automation_bridge": n8n_configured(),
            },
            "claude": {
                "configured": claude.configured,
                "model": claude.model if claude.configured else None,
            },
            "railway": _railway_runtime(),
        }

    return router
