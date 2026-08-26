from __future__ import annotations

import json
import os
from typing import Any

from atlas_n8n import call_tool, configured

TARGET_WORKFLOW = "ecomsx222"


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _payload(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return structured
    for block in getattr(result, "content", []) or []:
        text = getattr(block, "text", None)
        if not text:
            continue
        try:
            return json.loads(text)
        except Exception:
            continue
    return None


def _find_workflow(value: Any, wanted: str) -> dict | None:
    if isinstance(value, dict):
        name = str(value.get("name") or "").strip()
        if name.lower() == wanted.lower() and (value.get("id") or value.get("workflowId")):
            return value
        for child in value.values():
            found = _find_workflow(child, wanted)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_workflow(child, wanted)
            if found:
                return found
    return None


def _find_workflow_body(value: Any) -> dict | None:
    if isinstance(value, dict):
        if isinstance(value.get("nodes"), list) and isinstance(value.get("connections"), dict):
            return value
        for child in value.values():
            found = _find_workflow_body(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_workflow_body(child)
            if found:
                return found
    return None


def _safe_params(node: dict[str, Any]) -> dict[str, Any]:
    params = node.get("parameters")
    if not isinstance(params, dict):
        return {}
    node_type = str(node.get("type") or "")
    if node_type == "n8n-nodes-base.httpRequest":
        return {k: params.get(k) for k in ("method", "url", "authentication", "nodeCredentialType", "sendBody") if k in params}
    if node_type == "n8n-nodes-base.github":
        return {k: params.get(k) for k in ("resource", "operation", "owner", "repository", "filePath", "commitMessage", "authentication") if k in params}
    if node_type == "@n8n/n8n-nodes-langchain.anthropic":
        safe = {"modelId": params.get("modelId")}
        messages = params.get("messages")
        if messages is not None:
            safe["messages"] = messages
        options = params.get("options")
        if isinstance(options, dict):
            safe["option_keys"] = sorted(options.keys())
        return safe
    return {}


def _collect_nodes(value: Any) -> list[dict[str, Any]]:
    body = _find_workflow_body(value)
    if not body:
        return []
    nodes: list[dict[str, Any]] = []
    for node in body.get("nodes", []):
        if not isinstance(node, dict):
            continue
        params = node.get("parameters")
        nodes.append({
            "name": node.get("name"),
            "type": node.get("type"),
            "typeVersion": node.get("typeVersion"),
            "disabled": node.get("disabled", False),
            "position": node.get("position"),
            "parameter_keys": sorted(params.keys()) if isinstance(params, dict) else [],
            "credential_types": sorted((node.get("credentials") or {}).keys()) if isinstance(node.get("credentials"), dict) else [],
            "safe_parameters": _safe_params(node),
        })
    return nodes


async def maybe_inspect_ecomsx222(logger) -> None:
    if not _enabled("N8N_INSPECT_ECOMSX222"):
        return
    if not configured():
        logger.warning("ECOMSX222_INSPECT_RESULT ok=false error=n8n_not_configured")
        return

    try:
        search = await call_tool("search_workflows", {"query": TARGET_WORKFLOW, "limit": 50})
        search_payload = _payload(search)
        workflow = _find_workflow(search_payload, TARGET_WORKFLOW)
        if not workflow:
            logger.warning("ECOMSX222_INSPECT_RESULT ok=false error=workflow_not_found query=%s payload=%s", TARGET_WORKFLOW, json.dumps(search_payload, ensure_ascii=False, default=str)[:2500])
            return

        workflow_id = workflow.get("id") or workflow.get("workflowId")
        details = await call_tool("get_workflow_details", {"workflowId": workflow_id, "detailLevel": "full"})
        details_payload = _payload(details)
        body = _find_workflow_body(details_payload) or {}
        nodes = _collect_nodes(details_payload)
        summary = {
            "ok": True,
            "workflow_id": workflow_id,
            "name": workflow.get("name") or TARGET_WORKFLOW,
            "active": body.get("active"),
            "node_count": len(nodes),
            "nodes": nodes,
            "connections": body.get("connections", {}),
        }
        logger.info("ECOMSX222_INSPECT_RESULT %s", json.dumps(summary, ensure_ascii=False, default=str)[:30000])
    except Exception as exc:
        logger.exception("ECOMSX222_INSPECT_RESULT ok=false error=%s", type(exc).__name__)
