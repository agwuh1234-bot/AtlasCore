"""ASGI entrypoint for Atlas with runtime integrations enabled."""

from atlas_entry import atlas
from atlas_n8n_executor import build_n8n_executor_router

api = atlas.api
api.include_router(build_n8n_executor_router(bridge_key=atlas.ATLAS_BRIDGE_KEY))
