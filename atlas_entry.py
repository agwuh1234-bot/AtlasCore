"""Atlas runtime entrypoint with n8n MCP integration.

Keeps n8n credentials in environment variables and exposes the n8n MCP server
to Atlas through two narrow tools: discovery and invocation.
"""

import json

import main as atlas
from atlas_n8n import N8NBridgeError, call_tool as n8n_call, configured as n8n_configured, list_tools as n8n_list


N8N_TOOLS = [
    {
        "type": "function",
        "name": "n8n_list_tools",
        "description": "List the tools exposed by the connected n8n instance-level MCP server. Use this before an n8n operation when the exact MCP tool name or arguments are unknown.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "n8n_call_tool",
        "description": "Call one tool exposed by the connected n8n MCP server. First discover the exact tool name and schema with n8n_list_tools. arguments_json must be a JSON object encoded as a string.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "arguments_json": {"type": "string"},
            },
            "required": ["name", "arguments_json"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

_existing_names = {item.get("name") for item in atlas.TOOLS if item.get("type") == "function"}
for item in N8N_TOOLS:
    if item["name"] not in _existing_names:
        atlas.TOOLS.append(item)

atlas.SYSTEM_PROMPT += """

n8n integration:
- You can control the connected n8n instance through n8n_list_tools and n8n_call_tool.
- Discover the current n8n MCP tool schema before calling an unfamiliar n8n operation.
- For requests to inspect or change n8n workflows, use the n8n tools instead of guessing UI steps.
- Do not expose credentials, access tokens, API keys, or secret environment values.
- Do not claim an n8n change succeeded unless the MCP tool returned success.
"""

_original_execute_tool = atlas.execute_tool


def _mcp_result_to_json(result):
    payload = {
        "ok": not bool(getattr(result, "isError", False)),
        "is_error": bool(getattr(result, "isError", False)),
    }
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        payload["structured_content"] = structured
    content = []
    for block in getattr(result, "content", []) or []:
        if hasattr(block, "text"):
            content.append({"type": "text", "text": block.text})
        else:
            content.append({"type": type(block).__name__, "value": str(block)})
    payload["content"] = content
    return json.dumps(payload, ensure_ascii=False, default=str)


async def execute_tool(name, arguments, run_context=None):
    if name == "n8n_list_tools":
        if not n8n_configured():
            return json.dumps({"ok": False, "error": "n8n_not_configured"}, ensure_ascii=False)
        try:
            tools = await n8n_list()
            return json.dumps({"ok": True, "tools": tools}, ensure_ascii=False, default=str)
        except N8NBridgeError as exc:
            return json.dumps({"ok": False, "error": "n8n_bridge_error", "detail": str(exc)}, ensure_ascii=False)
        except Exception as exc:
            atlas.logger.exception("n8n MCP tool discovery failed")
            return json.dumps({"ok": False, "error": "n8n_list_tools_failed", "detail": type(exc).__name__}, ensure_ascii=False)

    if name == "n8n_call_tool":
        if not n8n_configured():
            return json.dumps({"ok": False, "error": "n8n_not_configured"}, ensure_ascii=False)
        try:
            raw_arguments = arguments.get("arguments_json", "{}") or "{}"
            parsed_arguments = json.loads(raw_arguments)
            if not isinstance(parsed_arguments, dict):
                raise ValueError("arguments_json must encode a JSON object")
            result = await n8n_call(arguments["name"], parsed_arguments)
            return _mcp_result_to_json(result)
        except (json.JSONDecodeError, ValueError) as exc:
            return json.dumps({"ok": False, "error": "invalid_n8n_arguments", "detail": str(exc)}, ensure_ascii=False)
        except N8NBridgeError as exc:
            return json.dumps({"ok": False, "error": "n8n_bridge_error", "detail": str(exc)}, ensure_ascii=False)
        except Exception as exc:
            atlas.logger.exception("n8n MCP call failed")
            return json.dumps({"ok": False, "error": "n8n_call_failed", "detail": type(exc).__name__}, ensure_ascii=False)

    return await _original_execute_tool(name, arguments, run_context)


atlas.execute_tool = execute_tool


if __name__ == "__main__":
    atlas.main()
