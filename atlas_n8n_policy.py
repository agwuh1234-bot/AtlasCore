"""Safety policy for Atlas n8n MCP calls.

The policy is intentionally conservative: unknown tools are treated as writes.
Destructive tools require a separate opt-in from ordinary writes.
"""

import os
import re

READ_PREFIXES = (
    "get_", "list_", "search_", "find_", "read_", "inspect_", "describe_",
    "status_", "health_", "lookup_", "query_", "fetch_",
)
READ_SUFFIXES = ("_get", "_list", "_search", "_find", "_read", "_status", "_health")
DESTRUCTIVE_MARKERS = (
    "delete", "remove", "destroy", "purge", "drop", "deactivate", "disable", "archive",
    "reset", "clear", "revoke", "terminate", "cancel",
)
WRITE_MARKERS = (
    "create", "update", "edit", "write", "save", "activate", "enable", "execute", "run",
    "trigger", "import", "duplicate", "copy", "move", "rename", "publish", "deploy",
)


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def classify_tool(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    if any(marker in normalized for marker in DESTRUCTIVE_MARKERS):
        return "destructive"
    if normalized.startswith(READ_PREFIXES) or normalized.endswith(READ_SUFFIXES):
        return "read"
    if any(marker in normalized for marker in WRITE_MARKERS):
        return "write"
    return "write"


def decision(name: str, declared_intent: str) -> tuple[bool, str]:
    actual = classify_tool(name)
    intent = (declared_intent or "").strip().lower()
    if intent not in {"read", "write"}:
        return False, "invalid_intent"
    if actual == "read":
        return (intent == "read", "ok" if intent == "read" else "intent_mismatch")
    if intent != "write":
        return False, "intent_mismatch"
    if actual == "destructive":
        enabled = _flag("N8N_DESTRUCTIVE_ENABLED")
        return enabled, "ok" if enabled else "destructive_disabled"
    enabled = _flag("N8N_WRITES_ENABLED")
    return enabled, "ok" if enabled else "writes_disabled"


def preflight(tools: list[dict], name: str, declared_intent: str) -> dict:
    """Validate a proposed MCP call without executing it.

    Requires an exact tool-name match from live discovery and returns only public
    schema/policy metadata. This lets Atlas reason about a call before any side effect.
    """
    tool_name = (name or "").strip()
    match = next((tool for tool in tools if str(tool.get("name") or "") == tool_name), None)
    if match is None:
        return {
            "ok": False,
            "found": False,
            "allowed": False,
            "classification": classify_tool(tool_name),
            "reason": "unknown_tool",
        }
    allowed, reason = decision(tool_name, declared_intent)
    return {
        "ok": True,
        "found": True,
        "allowed": allowed,
        "classification": classify_tool(tool_name),
        "reason": reason,
        "name": tool_name,
        "description": match.get("description") or "",
        "input_schema": match.get("inputSchema") or {},
    }
