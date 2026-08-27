"""n8n MCP bridge for Atlas.

Secrets are read only from environment variables. Never commit the n8n access token.
All MCP calls pass through the central Atlas n8n safety policy before execution.
"""

import asyncio
import copy
import math
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
    allowed, reason = decision(tool_name, "read")
    if allowed:
        return "read"
    if reason == "intent_mismatch":
        return "write"
    return "write"


def _is_partial_workflow_tool(tool_name: str) -> bool:
    normalized = (tool_name or "").strip().lower()
    return normalized == "update_workflow" or normalized.endswith("update_partial_workflow")


_NON_DESTRUCTIVE_PARTIAL_OPERATIONS = {
    "addnode",
    "updatenode",
    "updatenodeparameters",
    "addconnection",
}


def _contains_destructive_workflow_operation(arguments: dict) -> bool:
    operations = arguments.get("operations")
    if not isinstance(operations, list):
        return True
    for operation in operations:
        if not isinstance(operation, dict):
            return True
        op_type = str(operation.get("type") or "").strip().lower()
        if not op_type:
            return True
        if op_type.startswith("remove") or op_type.startswith("delete"):
            return True
        if op_type == "setnodedisabled":
            if operation.get("disabled") is True:
                return True
            if operation.get("disabled") is False:
                continue
            return True
        if op_type in {
            "disablenode",
            "deactivateworkflow",
            "replaceconnections",
            "rewireconnection",
            "cleanstaleconnections",
        }:
            return True
        if op_type not in _NON_DESTRUCTIVE_PARTIAL_OPERATIONS:
            return True
    return False


def _authorize_call(tool_name: str, arguments: dict) -> None:
    intent = _declared_intent(tool_name)
    allowed, reason = decision(tool_name, intent)
    if not allowed:
        raise N8NBridgeError(f"n8n MCP call blocked by policy: {reason}")

    if _is_partial_workflow_tool(tool_name) and _contains_destructive_workflow_operation(arguments):
        destructive_enabled = os.environ.get("N8N_DESTRUCTIVE_ENABLED", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        if not destructive_enabled:
            raise N8NBridgeError("n8n MCP call blocked by policy: destructive_disabled")


def _matches_schema_type(value, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "null":
        return value is None
    return True


def _matches_declared_type(value, expected) -> bool:
    if isinstance(expected, str):
        return _matches_schema_type(value, expected)
    if isinstance(expected, list):
        declared = [item for item in expected if isinstance(item, str)]
        if not declared:
            return False
        return any(_matches_schema_type(value, item) for item in declared)
    return True


def _validate_size_constraints(key: str, value, prop: dict) -> None:
    if isinstance(value, str):
        min_length = prop.get("minLength")
        max_length = prop.get("maxLength")
        if isinstance(min_length, int) and len(value) < min_length:
            raise N8NBridgeError(
                f"n8n tool arguments failed schema validation: {key} is shorter than minLength"
            )
        if isinstance(max_length, int) and len(value) > max_length:
            raise N8NBridgeError(
                f"n8n tool arguments failed schema validation: {key} exceeds maxLength"
            )

    if isinstance(value, list):
        min_items = prop.get("minItems")
        max_items = prop.get("maxItems")
        if isinstance(min_items, int) and len(value) < min_items:
            raise N8NBridgeError(
                f"n8n tool arguments failed schema validation: {key} has fewer than minItems"
            )
        if isinstance(max_items, int) and len(value) > max_items:
            raise N8NBridgeError(
                f"n8n tool arguments failed schema validation: {key} exceeds maxItems"
            )


def _validate_numeric_constraints(key: str, value, prop: dict) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise N8NBridgeError(
            f"n8n tool arguments failed schema validation: {key} must be a finite number"
        )

    minimum = prop.get("minimum")
    maximum = prop.get("maximum")
    exclusive_minimum = prop.get("exclusiveMinimum")
    exclusive_maximum = prop.get("exclusiveMaximum")

    if isinstance(minimum, (int, float)) and value < minimum:
        raise N8NBridgeError(
            f"n8n tool arguments failed schema validation: {key} is below minimum"
        )
    if isinstance(maximum, (int, float)) and value > maximum:
        raise N8NBridgeError(
            f"n8n tool arguments failed schema validation: {key} exceeds maximum"
        )
    if isinstance(exclusive_minimum, (int, float)) and not isinstance(exclusive_minimum, bool) and value <= exclusive_minimum:
        raise N8NBridgeError(
            f"n8n tool arguments failed schema validation: {key} must exceed exclusiveMinimum"
        )
    if isinstance(exclusive_maximum, (int, float)) and not isinstance(exclusive_maximum, bool) and value >= exclusive_maximum:
        raise N8NBridgeError(
            f"n8n tool arguments failed schema validation: {key} must be below exclusiveMaximum"
        )


def _validate_arguments_against_schema(arguments: dict, schema) -> None:
    """Fail closed on clear top-level schema mismatches before invoking n8n."""
    if not isinstance(schema, dict):
        return

    required = schema.get("required")
    if isinstance(required, list):
        missing = [key for key in required if isinstance(key, str) and key not in arguments]
        if missing:
            raise N8NBridgeError(
                "n8n tool arguments failed schema validation: missing required field(s): "
                + ", ".join(sorted(missing))
            )

    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return

    if schema.get("additionalProperties") is False:
        undeclared = sorted(key for key in arguments if key not in properties)
        if undeclared:
            raise N8NBridgeError(
                "n8n tool arguments failed schema validation: undeclared field(s): "
                + ", ".join(undeclared)
            )

    for key, value in arguments.items():
        prop = properties.get(key)
        if not isinstance(prop, dict):
            continue
        expected = prop.get("type")
        if isinstance(expected, (str, list)) and not _matches_declared_type(value, expected):
            expected_label = expected if isinstance(expected, str) else " or ".join(
                item for item in expected if isinstance(item, str)
            )
            raise N8NBridgeError(
                f"n8n tool arguments failed schema validation: {key} must be {expected_label or 'a declared type'}"
            )
        if "const" in prop and value != prop.get("const"):
            raise N8NBridgeError(
                f"n8n tool arguments failed schema validation: {key} does not match const"
            )
        allowed_values = prop.get("enum")
        if isinstance(allowed_values, list) and value not in allowed_values:
            raise N8NBridgeError(
                f"n8n tool arguments failed schema validation: {key} is not an allowed value"
            )
        _validate_size_constraints(key, value, prop)
        _validate_numeric_constraints(key, value, prop)


async def call_tool(name: str, arguments: dict | None = None):
    tool_name = (name or "").strip()
    if not tool_name:
        raise N8NBridgeError("n8n tool name is required")
    if arguments is not None and not isinstance(arguments, dict):
        raise N8NBridgeError("n8n tool arguments must be an object")

    try:
        call_arguments = {} if arguments is None else copy.deepcopy(arguments)
    except Exception as exc:
        raise N8NBridgeError("n8n tool arguments could not be safely snapshotted") from exc

    async with n8n_session() as session:
        discovered = await _await_mcp(session.list_tools(), "tool discovery")
        discovered_tool = next((tool for tool in discovered.tools if tool.name == tool_name), None)
        if discovered_tool is None:
            raise N8NBridgeError(f"Unknown n8n MCP tool: {tool_name}")
        _authorize_call(tool_name, call_arguments)
        _validate_arguments_against_schema(call_arguments, getattr(discovered_tool, "inputSchema", None))
        return await _await_mcp(session.call_tool(tool_name, call_arguments), f"tool call {tool_name}")