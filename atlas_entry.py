"""Atlas runtime entrypoint with n8n MCP integration."""

import asyncio
import json
import os
from contextlib import asynccontextmanager

import main as atlas
from atlas_n8n import N8NBridgeError, call_tool as n8n_call, configured as n8n_configured, list_tools as n8n_list
from atlas_n8n_bootstrap import maybe_add_ping_node, maybe_add_second_test_node, maybe_bootstrap_test_workflow
from atlas_n8n_ecom import maybe_inspect_ecomsx222
from atlas_n8n_policy import decision as n8n_policy_decision, preflight as n8n_preflight

N8N_TOOLS = [
    {
        "type": "function",
        "name": "n8n_list_tools",
        "description": "List the tools exposed by the connected n8n instance-level MCP server. Use this before an n8n operation when the exact MCP tool name or arguments are unknown.",
        "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        "strict": True,
    },
    {
        "type": "function",
        "name": "n8n_preflight_tool",
        "description": "Safely validate one proposed n8n MCP call before execution. Confirms the tool exists in live discovery, returns its public input schema, classifies it as read/write/destructive, and reports whether current server policy allows the declared intent. This tool never executes the n8n operation.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "intent": {"type": "string", "enum": ["read", "write"]},
            },
            "required": ["name", "intent"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "n8n_call_tool",
        "description": "Call one tool exposed by the connected n8n instance-level MCP server. First validate unfamiliar or mutating operations with n8n_preflight_tool. Declare intent=read for inspection/list/get operations and intent=write for mutations. Writes are server-policy gated and destructive operations have a separate gate.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "arguments_json": {"type": "string"},
                "intent": {"type": "string", "enum": ["read", "write"]},
            },
            "required": ["name", "arguments_json", "intent"],
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
- You can control the connected n8n instance through n8n_list_tools, n8n_preflight_tool, and n8n_call_tool.
- Discover the current n8n MCP tool schema before calling an unfamiliar n8n operation.
- Before any unfamiliar or mutating n8n call, use n8n_preflight_tool and obey its found/allowed result and returned input schema.
- For requests to inspect or change n8n workflows, use the n8n tools instead of guessing UI steps.
- Set intent=read only for non-mutating inspection calls. Set intent=write for any operation that creates, edits, runs, activates, imports, moves, or otherwise changes state.
- Unknown n8n tool names are treated as writes by policy. Destructive operations such as delete/deactivate require a separate server-side opt-in.
- If policy blocks a call, do not retry it by changing the declared intent; report that the operation is blocked by safety policy.
- Do not expose credentials, access tokens, API keys, or secret environment values.
- Do not claim an n8n change succeeded unless the MCP tool returned success.
"""

_original_execute_tool = atlas.execute_tool


def _mcp_result_to_json(result):
    payload = {"ok": not bool(getattr(result, "isError", False)), "is_error": bool(getattr(result, "isError", False))}
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

    if name == "n8n_preflight_tool":
        if not n8n_configured():
            return json.dumps({"ok": False, "error": "n8n_not_configured"}, ensure_ascii=False)
        tool_name = str(arguments.get("name") or "").strip()
        intent = str(arguments.get("intent") or "").strip().lower()
        try:
            tools = await n8n_list()
            return json.dumps(n8n_preflight(tools, tool_name, intent), ensure_ascii=False, default=str)
        except N8NBridgeError as exc:
            return json.dumps({"ok": False, "error": "n8n_bridge_error", "detail": str(exc)}, ensure_ascii=False)
        except Exception as exc:
            atlas.logger.exception("n8n MCP preflight failed")
            return json.dumps({"ok": False, "error": "n8n_preflight_failed", "detail": type(exc).__name__}, ensure_ascii=False)

    if name == "n8n_call_tool":
        if not n8n_configured():
            return json.dumps({"ok": False, "error": "n8n_not_configured"}, ensure_ascii=False)
        tool_name = str(arguments.get("name") or "").strip()
        intent = str(arguments.get("intent") or "").strip().lower()
        allowed, reason = n8n_policy_decision(tool_name, intent)
        if not allowed:
            atlas.logger.warning("N8N_POLICY_BLOCK tool=%s intent=%s reason=%s", tool_name[:80], intent[:16], reason)
            return json.dumps({"ok": False, "error": "n8n_policy_blocked", "reason": reason}, ensure_ascii=False)
        try:
            parsed_arguments = json.loads(arguments.get("arguments_json", "{}") or "{}")
            if not isinstance(parsed_arguments, dict):
                raise ValueError("arguments_json must encode a JSON object")
            result = await n8n_call(tool_name, parsed_arguments)
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


_original_run_atlas = atlas.run_atlas


def _claude_failure_message(review):
    error = str((review or {}).get("error") or "claude_review_failed")
    if error == "claude_not_configured":
        return "Claude не подключён к Atlas."
    if error == "claude_daily_limit_reached":
        return "Дневной лимит Claude исчерпан."
    if error == "claude_api_error":
        status = (review or {}).get("status")
        return f"Claude API вернул ошибку {status}." if status else "Claude API вернул ошибку."
    if error == "claude_request_failed":
        return "Claude не ответил из-за ошибки соединения."
    return "Проверка Claude не выполнена."


async def run_atlas(
    text,
    previous_response_id=None,
    allow_writes=True,
    attachments=None,
    claude_review=False,
    project_id="project-general",
    job_id=None,
):
    """Run Atlas and make the Claude-review switch deterministic.

    Normal Atlas requests keep the original execution path. When Claude review is
    requested, Atlas first produces its own answer and Claude then receives that
    exact answer plus the original task for an independent critique. The review
    is appended visibly, so the UI can never claim Claude checked a response when
    no Claude call happened.
    """
    draft = await _original_run_atlas(
        text,
        previous_response_id,
        allow_writes=allow_writes,
        attachments=attachments,
        claude_review=False,
        project_id=project_id,
        job_id=job_id,
    )
    if not claude_review:
        return draft

    review = None
    if not atlas.ANTHROPIC_API_KEY:
        review = {"ok": False, "error": "claude_not_configured"}
    elif not atlas.BUDGET.allow_claude():
        review = {"ok": False, "error": "claude_daily_limit_reached"}
    else:
        review_prompt = (
            "Ты независимый ревьюер результата Atlas. Проверь ответ по исходной задаче. "
            "Ищи фактические ошибки, пропущенные риски, неверные утверждения и конкретные исправления. "
            "Не переписывай всё без необходимости. Формат: Вердикт; Ошибки/риски; Что исправить.\n\n"
            f"Исходная задача пользователя:\n{str(text or '')[:4500]}\n\n"
            f"Ответ Atlas:\n{str(draft.output_text or '')[:6500]}"
        )
        raw_review = await atlas.claude_ask(review_prompt)
        try:
            review = json.loads(raw_review) if isinstance(raw_review, str) else raw_review
        except (TypeError, ValueError):
            review = {"ok": False, "error": "claude_review_invalid_response"}

    usage = dict(draft.usage or {})
    if isinstance(review, dict) and review.get("ok") and str(review.get("answer") or "").strip():
        model = str(review.get("model") or atlas.CLAUDE_MODEL)
        answer = str(review.get("answer") or "").strip()
        try:
            normalized_project = atlas.STORE._project_id(project_id)
            atlas.BUDGET.record_claude(job_id, normalized_project, model)
        except Exception:
            atlas.logger.exception("Failed to record Claude review usage")
        atlas.logger.info("CLAUDE_REVIEW ok=true model=%s", model[:80])
        usage["claude_review"] = {"ok": True, "model": model}
        output_text = f"{draft.output_text}\n\n### Проверка Claude\n{answer}".strip()
    else:
        review = review if isinstance(review, dict) else {"ok": False, "error": "claude_review_failed"}
        atlas.logger.warning(
            "CLAUDE_REVIEW ok=false error=%s status=%s",
            str(review.get("error") or "unknown")[:80],
            str(review.get("status") or "")[:16],
        )
        usage["claude_review"] = {
            "ok": False,
            "error": str(review.get("error") or "claude_review_failed")[:80],
        }
        output_text = f"{draft.output_text}\n\n### Проверка Claude\n{_claude_failure_message(review)}".strip()

    return atlas.AtlasRunResult(
        id=draft.id,
        output_text=output_text,
        model=draft.model,
        route=draft.route,
        usage=usage,
    )


atlas.run_atlas = run_atlas


async def _probe_n8n():
    if not n8n_configured():
        atlas.logger.warning("N8N_MCP_PROBE configured=false")
        return
    try:
        tools = await asyncio.wait_for(n8n_list(), timeout=10)
        atlas.logger.info("N8N_MCP_PROBE ok=true tool_count=%d", len(tools))
        if os.environ.get("N8N_DEBUG_DISCOVERY", "").strip().lower() in {"1", "true", "yes", "on"}:
            for tool in tools:
                name = str(tool.get("name") or "")
                lowered = name.lower()
                if "workflow" in lowered and any(word in lowered for word in ("create", "list", "search", "get", "update", "edit", "patch")):
                    atlas.logger.info(
                        "N8N_TOOL_DISCOVERY name=%s schema=%s",
                        name[:120],
                        json.dumps(tool.get("inputSchema") or {}, ensure_ascii=False, default=str)[:5000],
                    )
    except asyncio.TimeoutError:
        atlas.logger.warning("N8N_MCP_PROBE ok=false error=timeout")
    except Exception as exc:
        atlas.logger.warning("N8N_MCP_PROBE ok=false error=%s", type(exc).__name__)


async def _probe_claude():
    if os.environ.get("CLAUDE_STARTUP_PROBE", "").strip() != "1":
        return
    if not atlas.ANTHROPIC_API_KEY:
        atlas.logger.warning("CLAUDE_STARTUP_PROBE ok=false configured=false")
        return
    try:
        async with atlas.httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                "https://api.anthropic.com/v1/models",
                headers={
                    "x-api-key": atlas.ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                },
                params={"limit": 100},
            )
        if response.status_code != 200:
            atlas.logger.warning("CLAUDE_STARTUP_PROBE ok=false status=%s", response.status_code)
            return
        data = response.json()
        model_ids = {
            str(item.get("id") or "")
            for item in (data.get("data") or [])
            if isinstance(item, dict)
        }
        available = atlas.CLAUDE_MODEL in model_ids
        log = atlas.logger.info if available else atlas.logger.warning
        log(
            "CLAUDE_STARTUP_PROBE ok=%s model=%s available=%s visible_models=%d",
            str(available).lower(),
            atlas.CLAUDE_MODEL[:80],
            str(available).lower(),
            len(model_ids),
        )
    except Exception as exc:
        atlas.logger.warning("CLAUDE_STARTUP_PROBE ok=false error=%s", type(exc).__name__)


@atlas.api.get("/integrations/n8n/health")
async def n8n_health():
    if not n8n_configured():
        return {"ok": False, "configured": False, "error": "n8n_not_configured"}
    try:
        tools = await asyncio.wait_for(n8n_list(), timeout=10)
        return {"ok": True, "configured": True, "tool_count": len(tools)}
    except N8NBridgeError:
        return {"ok": False, "configured": True, "error": "n8n_bridge_error"}
    except Exception:
        return {"ok": False, "configured": True, "error": "n8n_probe_failed"}


_original_lifespan = atlas.api.router.lifespan_context

@asynccontextmanager
async def _atlas_lifespan_with_n8n(app):
    async with _original_lifespan(app):
        await _probe_claude()
        await _probe_n8n()
        await maybe_bootstrap_test_workflow(atlas.logger)
        await maybe_add_second_test_node(atlas.logger)
        await maybe_add_ping_node(atlas.logger)
        await maybe_inspect_ecomsx222(atlas.logger)
        yield

atlas.api.router.lifespan_context = _atlas_lifespan_with_n8n

if __name__ == "__main__":
    atlas.main()
