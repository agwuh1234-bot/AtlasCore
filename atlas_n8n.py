"""n8n MCP bridge for Atlas.

Secrets are read only from environment variables. Never commit the n8n access token.
All MCP calls pass through the central Atlas n8n safety policy before execution.
"""

import asyncio
import os
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from atlas_n8n_policy import decision


N8N_MCP_URL = os.environ.get("N8N_MCP_URL", "").strip()
N8N_MCP_TOKEN = os.environ.get("N8N_MCP_TOKEN", "").strip()


class N8NBridgeError(RuntimeError):
    pass


def configured() -> bool:
    return bool(N8N_MCP_URL and N8N_MCP_TOKEN)


def _timeout_seconds() -> float:
    """Return a bounded MCP operation timeout without trusting environment input."""
    raw = os.environ.get("N8N_MCP_TIMEOUT_SECONDS", "20").strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 20.0
    return min(120.0, max(1.0, value))


async def _await_mcp(awaitable, operation: str):
    try:
        return await asyncio.wait_for(awaitable, timeout=_timeout_seconds())
    except TimeoutError as exc:
        raise N8NBridgeError(f"n8n MCP {operation} timed out") from exc


@asynccontextmanager
async def n8n_session():
    if not configured():
        raise N8NBridgeError("N8N_MCP_URL and N8N_MCP_TOKEN must be configured")

    headers = {"Authorization": f"Bearer {N8N_MCP_TOKEN}"}
    async with streamablehttp_client(N8N_MCP_URL, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await _await_mcp(session.initialize(), "initialize")
            yield session


async def list_tools():
    async with n8n_session() as session:
        result = await _await_mcp(session.list_tools(), "tool discovery")
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema,
            }
            for tool in result.tools
        ]


def _declared_intent(tool_name: str) -> str:
    """Infer the narrowest intent accepted by policy for a discovered tool."""
    allowed, reason = decision(tool_name, "read")
    if allowed:
        return "read"
    if reason == "intent_mismatch":
        return "write"
    return "write"


def _contains_destructive_workflow_operation(arguments: dict) -> bool:
    operations = arguments.get("operations")
    if not isinstance(operations, list):
        return False
    for operation in operations:
        if not isinstance(operation, dict):
            continue
        op_type = str(operation.get("type") or "").strip().lower()
        if op_type.startswith("remove") or op_type.startswith("delete"):
            return True
    return False


def _authorize_call(tool_name: str, arguments: dict) -> None:
    intent = _declared_intent(tool_name)
    allowed, reason = decision(tool_name, intent)
    if not allowed:
        raise N8NBridgeError(f"n8n MCP call blocked by policy: {reason}")

    # update_workflow is nominally a write tool, but its structured operation list
    # can contain destructive actions. Require the separate destructive opt-in in
    # that case so ordinary write permission cannot silently remove topology.
    if tool_name == "update_workflow" and _contains_destructive_workflow_operation(arguments):
        destructive_enabled = os.environ.get("N8N_DESTRUCTIVE_ENABLED", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        if not destructive_enabled:
            raise N8NBridgeError("n8n MCP call blocked by policy: destructive_disabled")


async def call_tool(name: str, arguments: dict | None = None):
    tool_name = (name or "").strip()
    if not tool_name:
        raise N8NBridgeError("n8n tool name is required")
    if arguments is not None and not isinstance(arguments, dict):
        raise N8NBridgeError("n8n tool arguments must be an object")

    call_arguments = {} if arguments is None else arguments
    async with n8n_session() as session:
        discovered = await _await_mcp(session.list_tools(), "tool discovery")
        available_names = {tool.name for tool in discovered.tools}
        if tool_name not in available_names:
            raise N8NBridgeError(f"Unknown n8n MCP tool: {tool_name}")
        _authorize_call(tool_name, call_arguments)
        return await _await_mcp(session.call_tool(tool_name, call_arguments), f"tool call {tool_name}")
