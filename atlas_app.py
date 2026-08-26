"""ASGI entrypoint for Atlas with runtime integrations enabled."""

import os

from atlas_entry import atlas
from atlas_n8n_executor import build_n8n_executor_router

api = atlas.api
api.include_router(
    build_n8n_executor_router(
        bridge_key=atlas.ATLAS_BRIDGE_KEY,
        chatgpt_bridge_key=os.environ.get("CHATGPT_N8N_BRIDGE_KEY"),
    )
)
