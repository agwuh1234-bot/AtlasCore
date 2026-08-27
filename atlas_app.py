"""ASGI entrypoint for Atlas with runtime integrations enabled."""

import os

from atlas_entry import atlas
from atlas_executor_api import build_executor_router
from atlas_n8n_executor import build_n8n_executor_router
from atlas_code_api import build_code_router
from atlas_automation_api import build_automation_router
from atlas_automation_executions_api import build_automation_executions_router

api = atlas.api

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
