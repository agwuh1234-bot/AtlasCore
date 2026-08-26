"""n8n MCP bridge for Atlas.

Secrets are read only from environment variables. Never commit the n8n access token.
"""

import os
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


N8N_MCP_URL = os.environ.get("N8N_MCP_URL", "").strip()
N8N_MCP_TOKEN = os.environ.get("N8N_MCP_TOKEN", "").strip()


class N8NBridgeError(RuntimeError):
    pass


def configured() -> bool:
    return bool(N8N_MCP_URL and N8N_MCP_TOKEN)


@asynccontextmanager
async def n8n_session():
    if not configured():
        raise N8NBridgeError("N8N_MCP_URL and N8N_MCP_TOKEN must be configured")

    headers = {"Authorization": f"Bearer {N8N_MCP_TOKEN}"}
    async with streamablehttp_client(N8N_MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def list_tools():
    async with n8n_session() as session:
        result = await session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema,
            }
            for tool in result.tools
        ]


async def call_tool(name: str, arguments: dict | None = None):
    async with n8n_session() as session:
        return await session.call_tool(name, arguments or {})
