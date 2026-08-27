"""Read-only application API for the visual Atlas Automation Studio.

The UI can inspect live n8n workflow topology and policy state. It deliberately
cannot execute or mutate n8n directly: those actions continue through Atlas jobs,
preflight, write policy, and explicit user confirmation.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Request

from atlas_n8n import N8NBridgeError, call_tool, configured, list_tools
from atlas_n8n_ecom import (
    TARGET_WORKFLOW,
    TARGET_WORKFLOW_ID,
    _find_workflow_body,
    _payload,
    _workflow_safety_summary,
)
from atlas_n8n_graph_safety import connection_shape_issues
from atlas_n8n_policy import classify_tool, preflight


MAX_WORKFLOWS = 100
MAX_NODES = 250
MAX_EDGES = 600


def _tool(tools: list[dict[str, Any]], *names: str) -> dict[str, Any] | None:
    by_name = {str(item.get("name") or ""): item for item in tools}
    for name in names:
        if name in by_name:
            return by_name[name]
    return None


def _tool_can_call_without_args(tool: dict[str, Any] | None) -> bool:
    if not tool:
        return False
    schema = tool.get("inputSchema")
    if not isinstance(schema, dict):
        return True
    required = schema.get("required")
    return not isinstance(required, list) or len(required) == 0


def _collect_workflows(value: Any, output: list[dict[str, Any]], seen: set[str]) -> None:
    if len(output) >= MAX_WORKFLOWS:
        return
    if isinstance(value, dict):
        raw_id = value.get("workflowId", value.get("id"))
        name = value.get("name")
        looks_like_workflow = (
            isinstance(raw_id, (str, int))
            and isinstance(name, str)
            and bool(name.strip())
            and (
                "active" in value
                or "createdAt" in value
                or "updatedAt" in value
                or isinstance(value.get("nodes"), list)
            )
            and not isinstance(value.get("type"), str)
        )
        if looks_like_workflow:
            workflow_id = str(raw_id).strip()
            if workflow_id and workflow_id not in seen:
                seen.add(workflow_id)
                output.append(
                    {
                        "id": workflow_id,
                        "name": name.strip()[:200],
                        "active": value.get("active") if isinstance(value.get("active"), bool) else None,
                        "updated_at": value.get("updatedAt"),
                    }
                )
        for child in value.values():
            _collect_workflows(child, output, seen)
    elif isinstance(value, list):
        for child in value:
            _collect_workflows(child, output, seen)


def _edge_rows(body: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    connections = body.get("connections")
    if not isinstance(connections, dict):
        return rows
    for source, outputs in connections.items():
        if not isinstance(source, str) or not isinstance(outputs, dict):
            continue
        for output_type, branches in outputs.items():
            if not isinstance(branches, list):
                continue
            for branch_index, branch in enumerate(branches):
                if not isinstance(branch, list):
                    continue
                for edge in branch:
                    if len(rows) >= MAX_EDGES:
                        return rows
                    if not isinstance(edge, dict):
                        continue
                    target = edge.get("node")
                    if not isinstance(target, str) or not target:
                        continue
                    rows.append(
                        {
                            "source": source,
                            "target": target,
                            "type": str(edge.get("type") or output_type or "main"),
                            "branch": branch_index,
                            "index": edge.get("index") if isinstance(edge.get("index"), int) else 0,
                        }
                    )
    return rows


def _node_rows(body: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw_nodes = body.get("nodes")
    if not isinstance(raw_nodes, list):
        return rows
    for node in raw_nodes[:MAX_NODES]:
        if not isinstance(node, dict):
            continue
        name = str(node.get("name") or "").strip()
        if not name:
            continue
        params = node.get("parameters")
        credentials = node.get("credentials")
        position = node.get("position")
        if not (
            isinstance(position, list)
            and len(position) == 2
            and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in position)
        ):
            position = None
        rows.append(
            {
                "name": name[:200],
                "type": str(node.get("type") or "")[:240],
                "type_version": node.get("typeVersion"),
                "disabled": node.get("disabled") is True,
                "position": position,
                "parameter_keys": sorted(str(key) for key in params.keys())[:80] if isinstance(params, dict) else [],
                "credential_types": sorted(str(key) for key in credentials.keys())[:40]
                if isinstance(credentials, dict)
                else [],
            }
        )
    return rows


def _blocking_shape_issues(body: dict[str, Any]) -> list[str]:
    """Keep malformed/dangling/duplicate graph defects as UI blockers.

    n8n legitimately uses non-main connection types for AI/sub-node connections,
    so the Automation Studio does not label those supported n8n constructs unsafe.
    """
    issues = connection_shape_issues(body)
    prefixes = ("malformed_", "dangling_", "duplicate_")
    return [issue for issue in issues if issue.startswith(prefixes)]


def build_automation_router(*, verify_request: Callable) -> APIRouter:
    router = APIRouter(prefix="/app-automation", tags=["app", "automation"])

    def verify(request: Request, key: str | None) -> None:
        verify_request(request, key)

    @router.get("/status")
    async def status(
        request: Request,
        x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
    ):
        verify(request, x_atlas_key)
        if not configured():
            return {"ok": False, "configured": False, "tool_count": 0}
        try:
            tools = await list_tools()
        except N8NBridgeError as exc:
            raise HTTPException(status_code=502, detail={"error": "n8n_bridge_error", "detail": str(exc)})
        read_count = sum(1 for item in tools if classify_tool(str(item.get("name") or "")) == "read")
        write_count = len(tools) - read_count
        execute = preflight(tools, "execute_workflow", "write")
        update = preflight(tools, "update_workflow", "write")
        return {
            "ok": True,
            "configured": True,
            "tool_count": len(tools),
            "read_tool_count": read_count,
            "write_tool_count": write_count,
            "execute_policy": {
                "found": execute.get("found", False),
                "allowed": execute.get("allowed", False),
                "reason": execute.get("reason"),
            },
            "update_policy": {
                "found": update.get("found", False),
                "allowed": update.get("allowed", False),
                "reason": update.get("reason"),
            },
        }

    @router.get("/workflows")
    async def workflows(
        request: Request,
        x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
    ):
        verify(request, x_atlas_key)
        if not configured():
            return {"ok": False, "configured": False, "workflows": []}
        try:
            tools = await list_tools()
            list_tool = _tool(tools, "list_workflows", "get_workflows", "search_workflows")
            rows: list[dict[str, Any]] = []
            source = "fallback"
            if list_tool and _tool_can_call_without_args(list_tool):
                result = await call_tool(str(list_tool.get("name")), {})
                _collect_workflows(_payload(result), rows, set())
                source = str(list_tool.get("name"))
            if TARGET_WORKFLOW_ID not in {row["id"] for row in rows}:
                rows.insert(0, {"id": TARGET_WORKFLOW_ID, "name": TARGET_WORKFLOW, "active": None, "updated_at": None})
            return {"ok": True, "configured": True, "source": source, "workflows": rows[:MAX_WORKFLOWS]}
        except N8NBridgeError as exc:
            raise HTTPException(status_code=502, detail={"error": "n8n_bridge_error", "detail": str(exc)})

    @router.get("/workflow")
    async def workflow(
        request: Request,
        workflow_id: str,
        x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
    ):
        verify(request, x_atlas_key)
        workflow_id = str(workflow_id or "").strip()
        if not workflow_id or len(workflow_id) > 256:
            raise HTTPException(status_code=400, detail="Invalid workflow id")
        if not configured():
            raise HTTPException(status_code=503, detail="n8n_not_configured")
        try:
            tools = await list_tools()
            check = preflight(tools, "get_workflow_details", "read")
            if not check.get("found") or not check.get("allowed"):
                raise HTTPException(status_code=503, detail={"error": "workflow_read_unavailable", "preflight": check})
            result = await call_tool("get_workflow_details", {"workflowId": workflow_id, "detailLevel": "full"})
            payload = _payload(result)
            body = _find_workflow_body(payload)
            if not isinstance(body, dict):
                raise HTTPException(status_code=502, detail="n8n_workflow_shape_unavailable")
            nodes = _node_rows(body)
            edges = _edge_rows(body)
            blockers = _blocking_shape_issues(body)
            run_check = preflight(tools, "execute_workflow", "write")
            edit_check = preflight(tools, "update_workflow", "write")
            ecom_safety = None
            if workflow_id == TARGET_WORKFLOW_ID:
                ecom_safety = _workflow_safety_summary(payload)
            return {
                "ok": True,
                "workflow": {
                    "id": workflow_id,
                    "name": str(body.get("name") or (TARGET_WORKFLOW if workflow_id == TARGET_WORKFLOW_ID else workflow_id))[:200],
                    "active": body.get("active") if isinstance(body.get("active"), bool) else None,
                    "node_count": len(nodes),
                    "edge_count": len(edges),
                    "nodes": nodes,
                    "edges": edges,
                    "shape_ok": not blockers,
                    "shape_issues": blockers[:80],
                    "ecom_safety": ecom_safety,
                    "run_policy": {
                        "found": run_check.get("found", False),
                        "allowed": run_check.get("allowed", False),
                        "reason": run_check.get("reason"),
                    },
                    "edit_policy": {
                        "found": edit_check.get("found", False),
                        "allowed": edit_check.get("allowed", False),
                        "reason": edit_check.get("reason"),
                    },
                },
            }
        except HTTPException:
            raise
        except N8NBridgeError as exc:
            raise HTTPException(status_code=502, detail={"error": "n8n_bridge_error", "detail": str(exc)})

    return router
