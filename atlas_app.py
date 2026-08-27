"""ASGI entrypoint for Atlas with runtime integrations enabled."""

import os

from atlas_entry import atlas
from atlas_executor_api import build_executor_router
from atlas_n8n_executor import build_n8n_executor_router
from atlas_code_api import build_code_router
from atlas_automation_api import build_automation_router
from atlas_automation_executions_api import build_automation_executions_router
from atlas_integrations_status_api import build_integrations_status_router
from atlas_client_error_api import build_client_error_router

api = atlas.api


@api.middleware("http")
async def atlas_pwa_cache_policy(request, call_next):
    """Keep the installed Atlas app fresh while never caching live API state."""
    response = await call_next(request)
    path = request.url.path

    no_store = {
        "/",
        "/health",
        "/app/",
        "/app/index.html",
        "/app/sw.js",
        "/app/manifest.json",
    }
    if path in no_store or path.startswith("/app-") or path.startswith("/integrations/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif path.startswith("/app/") and path.endswith((".js", ".css", ".html", ".json")):
        response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"

    if path == "/app/sw.js":
        # The installed PWA starts at '/', so this worker must be allowed to
        # control the root document as well as /app/* assets.
        response.headers["Service-Worker-Allowed"] = "/"

    return response


# Authenticated browser-side exception telemetry. Only short redacted metadata
# is logged, never credentials or application storage.
api.include_router(
    build_client_error_router(
        verify_request=atlas.verify_app_request,
    )
)

# General authenticated executor, including Claude.
api.include_router(
    build_executor_router(
        bridge_key=atlas.ATLAS_BRIDGE_KEY,
    )
)

# Restricted n8n MCP executor for Atlas/ChatGPT automation.
api.include_router(
    build_n8n_executor_router(
        bridge_key=atlas.ATLAS_BRIDGE_KEY,
        chatgpt_bridge_key=os.environ.get("CHATGPT_N8N_BRIDGE_KEY"),
    )
)

# Read-only repository browser used by the visual Code Studio. Mutations still
# go through Atlas jobs + Developer Mode so existing safety policy stays intact.
api.include_router(
    build_code_router(
        verify_request=atlas.verify_app_request,
        repo=atlas.REPO,
        branch=atlas.GITHUB_BRANCH,
    )
)

# Read-only live n8n topology/status surface for Automation Studio. Workflow
# edits and executions remain behind Atlas jobs + n8n write policy/confirmation.
api.include_router(
    build_automation_router(
        verify_request=atlas.verify_app_request,
    )
)

# Read-only execution receipts/history for the selected n8n workflow. This
# exposes only bounded metadata, never execution payloads or credentials.
api.include_router(
    build_automation_executions_router(
        verify_request=atlas.verify_app_request,
    )
)

# Coarse integration capability/status flags used by the command-center UI.
# Secret values and credential identifiers are intentionally never returned.
api.include_router(
    build_integrations_status_router(
        verify_request=atlas.verify_app_request,
    )
)
