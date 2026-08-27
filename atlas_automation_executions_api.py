"""Read-only n8n execution history for Atlas Automation Studio."""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Request

from atlas_n8n import N8NBridgeError, call_tool, configured, list_tools
from atlas_n8n_ecom import _payload
from atlas_n8n_policy import classify_tool, preflight


MAX_EXECUTIONS = 24


def _execution_tool(tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    by_name = {str(item.get("name") or ""): item for item in tools}
    for name in ("list_executions", "get_executions", "search_executions"):
        item = by_name.get(name)
        if item and classify_tool(name) == "read":
            return item
    candidates = []
    for item in tools:
        name = str(item.get("name") or "").strip()
        lowered = name.lower()
        if (
            classify_tool(name) == "read"
            and "execution" in lowered
            and any(marker in lowered for marker in ("list", "search", "executions"))
        ):
            candidates.append(item)
    return sorted(candidates, key=lambda item: len(str(item.get("name") or "")))[0] if candidates else None


def _execution_arguments(tool: dict[str, Any], workflow_id: str, limit: int = 12) -> dict[str, Any] | None:
    schema = tool.get("inputSchema")
    if not isinstance(schema, dict):
        return {}
    properties = schema.get("properties")
    properties = properties if isinstance(properties, dict) else {}
    args: dict[str, Any] = {}

    for key in ("workflowId", "workflow_id", "workflowID"):
        if key in properties:
            args[key] = workflow_id
            break
    for key in ("limit", "pageSize", "page_size", "take"):
        if key in properties:
            prop = properties.get(key) if isinstance(properties.get(key), dict) else {}
            maximum = prop.get("maximum")
            requested = min(MAX_EXECUTIONS, max(1, int(limit)))
            if isinstance(maximum, (int, float)) and not isinstance(maximum, bool):
                requested = min(requested, max(1, int(maximum)))
            args[key] = requested
            break

    required = schema.get("required")
    if isinstance(required, list):
        missing = [key for key in required if isinstance(key, str) and key not in args]
        if missing:
            return None
    return args


def _scalar(value: Any, max_len: int = 256) -> str | None:
    if value is None or isinstance(value, (dict, list, tuple, set, bool)):
        return None
    text = str(value).strip()
    return text[:max_len] if text else None


def _looks_execution(value: dict[str, Any]) -> bool:
    if any(key in value for key in ("executionId", "execution_id")):
        return True
    if "id" not in value:
        return False
    return any(
        key in value
        for key in (
            "status",
            "startedAt",
            "started_at",
            "stoppedAt",
            "stopped_at",
            "finished",
            "finishedAt",
            "finished_at",
            "mode",
        )
    )


def _collect_executions(
    value: Any,
    output: list[dict[str, Any]],
    seen: set[str],
    workflow_id: str,
) -> None:
    if len(output) >= MAX_EXECUTIONS:
        return
    if isinstance(value, dict):
        if _looks_execution(value):
            execution_id = _scalar(value.get("executionId", value.get("execution_id", value.get("id"))))
            receipt_workflow_id = _scalar(value.get("workflowId", value.get("workflow_id")))
            if execution_id and execution_id not in seen and (
                not receipt_workflow_id or receipt_workflow_id == workflow_id
            ):
                seen.add(execution_id)
                raw_status = _scalar(value.get("status"), 64)
                finished = value.get("finished")
                if raw_status:
                    status = raw_status.lower()
                elif finished is True:
                    status = "success"
                elif finished is False:
                    status = "running"
                else:
                    status = "unknown"
                output.append(
                    {
                        "id": execution_id,
                        "workflow_id": receipt_workflow_id,
                        "status": status,
                        "mode": _scalar(value.get("mode"), 64),
                        "started_at": _scalar(value.get("startedAt", value.get("started_at")), 80),
                        "stopped_at": _scalar(
                            value.get(
                                "stoppedAt",
                                value.get("stopped_at", value.get("finishedAt", value.get("finished_at"))),
                            ),
                            80,
                        ),
                        "error_present": bool(value.get("error")),
                    }
                )
        for child in value.values():
            _collect_executions(child, output, seen, workflow_id)
    elif isinstance(value, list):
        for child in value:
            _collect_executions(child, output, seen, workflow_id)


def build_automation_executions_router(*, verify_request: Callable) -> APIRouter:
    router = APIRouter(prefix="/app-automation", tags=["app", "automation"])

    @router.get("/executions")
    async def executions(
        request: Request,
        workflow_id: str,
        limit: int = 12,
        x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
    ):
        verify_request(request, x_atlas_key)
        workflow_id = str(workflow_id or "").strip()
        if not workflow_id or len(workflow_id) > 256:
            raise HTTPException(status_code=400, detail="Invalid workflow id")
        if not configured():
            return {"ok": False, "configured": False, "available": False, "executions": []}
        try:
            tools = await list_tools()
            tool = _execution_tool(tools)
            if not tool:
                return {
                    "ok": True,
                    "configured": True,
                    "available": False,
                    "reason": "execution_history_tool_not_found",
                    "executions": [],
                }
            name = str(tool.get("name") or "")
            check = preflight(tools, name, "read")
            if not check.get("found") or not check.get("allowed"):
                return {
                    "ok": True,
                    "configured": True,
                    "available": False,
                    "reason": check.get("reason") or "execution_history_read_blocked",
                    "tool": name,
                    "executions": [],
                }
            arguments = _execution_arguments(tool, workflow_id, limit)
            if arguments is None:
                return {
                    "ok": True,
                    "configured": True,
                    "available": False,
                    "reason": "execution_history_schema_requires_unsupported_fields",
                    "tool": name,
                    "executions": [],
                }
            result = await call_tool(name, arguments)
            rows: list[dict[str, Any]] = []
            _collect_executions(_payload(result), rows, set(), workflow_id)
            return {
                "ok": True,
                "configured": True,
                "available": True,
                "tool": name,
                "executions": rows[: min(MAX_EXECUTIONS, max(1, int(limit)))],
            }
        except N8NBridgeError as exc:
            raise HTTPException(
                status_code=502,
                detail={"error": "n8n_bridge_error", "detail": str(exc)},
            )

    return router
