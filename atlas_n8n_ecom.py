from __future__ import annotations

import json
import os
from typing import Any

from atlas_n8n import call_tool, configured
from atlas_n8n_policy import decision

TARGET_WORKFLOW = "ecomsx222"
TARGET_WORKFLOW_ID = "0S8720gc3G2OODmG"
SHOPIFY_BRIEF_NODE = "Shopify Build Brief"


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
        if isinstance(messages, dict):
            values = messages.get("values")
            safe["message_count"] = len(values) if isinstance(values, list) else 0
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


def _has_node(value: Any, name: str) -> bool:
    return any(node.get("name") == name for node in _collect_nodes(value))


def _has_connection(body: dict[str, Any], source: str, target: str) -> bool:
    connections = body.get("connections")
    if not isinstance(connections, dict):
        return False
    source_map = connections.get(source)
    if not isinstance(source_map, dict):
        return False
    for outputs in source_map.values():
        if not isinstance(outputs, list):
            continue
        for branch in outputs:
            if not isinstance(branch, list):
                continue
            for edge in branch:
                if isinstance(edge, dict) and edge.get("node") == target:
                    return True
    return False


def _add_connection_if_missing(
    operations: list[dict[str, Any]],
    body: dict[str, Any],
    source: str,
    target: str,
) -> None:
    if not _has_connection(body, source, target):
        operations.append({"type": "addConnection", "source": source, "target": target})


def _workflow_safety_summary(value: Any) -> dict[str, Any]:
    body = _find_workflow_body(value) or {}
    nodes = _collect_nodes(value)
    by_name = {str(node.get("name")): node for node in nodes}
    issues: list[str] = []

    required_nodes = [
        "When clicking ‘Execute workflow’",
        SHOPIFY_BRIEF_NODE,
        "Message a model1",
        "Message a model",
    ]
    for name in required_nodes:
        if name not in by_name:
            issues.append(f"missing_node:{name}")

    required_edges = [
        ("When clicking ‘Execute workflow’", SHOPIFY_BRIEF_NODE),
        (SHOPIFY_BRIEF_NODE, "Message a model1"),
        ("Message a model1", "Message a model"),
    ]
    for source, target in required_edges:
        if not _has_connection(body, source, target):
            issues.append(f"missing_connection:{source}->{target}")

    forbidden_edges = [
        ("When clicking ‘Execute workflow’", "HTTP Request"),
        ("HTTP Request", "Message a model1"),
        ("Message a model", "Edit a file"),
    ]
    for source, target in forbidden_edges:
        if _has_connection(body, source, target):
            issues.append(f"unsafe_connection:{source}->{target}")

    for name in ("HTTP Request", "HTTP Request1", "Edit a file"):
        node = by_name.get(name)
        if node is not None and node.get("disabled") is not True:
            issues.append(f"unsafe_node_enabled:{name}")

    return {
        "ready_for_safe_manual_run": not issues,
        "issues": issues,
    }


async def maybe_upgrade_ecomsx222_shopify(logger) -> None:
    if not _enabled("N8N_UPGRADE_ECOMSX222_SHOPIFY"):
        return
    if not configured():
        logger.warning("ECOMSX222_SHOPIFY_RESULT ok=false error=n8n_not_configured")
        return

    allowed, reason = decision("update_workflow", "write")
    if not allowed:
        logger.warning("ECOMSX222_SHOPIFY_RESULT ok=false error=policy_blocked reason=%s", reason)
        return

    strategy_prompt = """=You are the Shopify commerce strategist for ecomSX222.\n\nSTORE CONTEXT FROM THE PREVIOUS NODE:\n{{ JSON.stringify($json) }}\n\nTurn the merchant request/context into a concrete Shopify implementation brief. Focus on conversion, product merchandising, navigation, trust, mobile UX, SEO, retention, and measurable outcomes. Prefer Shopify Online Store 2.0 patterns.\n\nRules:\n- This workflow is for Shopify/ecommerce work only. Never edit AtlasCore, main.py, repositories, branches, or infrastructure.\n- Never expose credentials or secrets.\n- Do not perform destructive store operations.\n- Separate facts from assumptions.\n- Return a concise implementation brief for the Shopify developer in the next step: objective, target pages/objects, exact changes, data needed, validation checklist, and expected KPI impact.\n- If store-specific information is missing, state what is missing instead of inventing it."""

    developer_prompt = """=You are the senior Shopify Online Store 2.0 developer for ecomSX222.\n\nSTRATEGY BRIEF:\n{{ JSON.stringify($json) }}\n\nProduce an implementation-ready Shopify package. Use Liquid, JSON templates, sections, blocks, metafields/metaobjects, CSS and minimal JavaScript when appropriate. Prefer native Shopify capabilities over unnecessary apps.\n\nRules:\n- Work only on Shopify/ecommerce scope. Never modify AtlasCore/main.py or GitHub automatically.\n- Never expose or hardcode API keys, tokens, passwords, cookies, or credentials.\n- Never delete products, customers, orders, themes, files, workflows, or data.\n- Treat live-store writes as requiring an explicit execution step; this workflow should prepare safe changes first.\n- Preserve mobile performance and accessibility.\n- Return: implementation plan, exact code/config snippets where useful, test checklist, rollback note, and next safe action.\n- Make outputs practical for a Basic-plan Shopify store in Germany using EUR."""

    brief_parameters = {
        "assignments": {
            "assignments": [
                {"id": "shop-platform", "name": "platform", "value": "Shopify", "type": "string"},
                {"id": "shop-domain", "name": "store_domain", "value": "z1egtm-1t.myshopify.com", "type": "string"},
                {"id": "shop-plan", "name": "plan", "value": "Basic", "type": "string"},
                {"id": "shop-market", "name": "market", "value": "Germany", "type": "string"},
                {"id": "shop-currency", "name": "currency", "value": "EUR", "type": "string"},
                {"id": "shop-stack", "name": "stack", "value": "Shopify Online Store 2.0 / Liquid", "type": "string"},
                {"id": "shop-scope", "name": "scope", "value": "conversion-focused ecommerce development", "type": "string"},
                {"id": "shop-safe", "name": "safe_mode", "value": True, "type": "boolean"},
            ]
        }
    }

    try:
        before_result = await call_tool("get_workflow_details", {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"})
        before = _payload(before_result)
        before_body = _find_workflow_body(before) or {}

        operations: list[dict[str, Any]] = []
        if not _has_node(before, SHOPIFY_BRIEF_NODE):
            operations.append({
                "type": "addNode",
                "node": {
                    "name": SHOPIFY_BRIEF_NODE,
                    "type": "n8n-nodes-base.set",
                    "typeVersion": 3.4,
                    "parameters": brief_parameters,
                    "position": [-920, 320],
                },
            })

        operations.extend([
            {"type": "updateNodeParameters", "nodeName": "Message a model1", "parameters": {"messages": {"values": [{"content": strategy_prompt}]}}},
            {"type": "updateNodeParameters", "nodeName": "Message a model", "parameters": {"messages": {"values": [{"content": developer_prompt}]}}},
            {"type": "setNodeDisabled", "nodeName": "HTTP Request", "disabled": True},
            {"type": "setNodeDisabled", "nodeName": "HTTP Request1", "disabled": True},
            {"type": "setNodeDisabled", "nodeName": "Edit a file", "disabled": True},
            {"type": "removeConnection", "source": "When clicking ‘Execute workflow’", "target": "HTTP Request", "ignoreErrors": True},
            {"type": "removeConnection", "source": "HTTP Request", "target": "Message a model1", "ignoreErrors": True},
            {"type": "removeConnection", "source": "Message a model", "target": "Edit a file", "ignoreErrors": True},
        ])

        _add_connection_if_missing(
            operations,
            before_body,
            "When clicking ‘Execute workflow’",
            SHOPIFY_BRIEF_NODE,
        )
        _add_connection_if_missing(
            operations,
            before_body,
            SHOPIFY_BRIEF_NODE,
            "Message a model1",
        )

        result = await call_tool("update_workflow", {"workflowId": TARGET_WORKFLOW_ID, "operations": operations})
        result_payload = _payload(result)

        verify_result = await call_tool("get_workflow_details", {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"})
        verify = _payload(verify_result)
        body = _find_workflow_body(verify) or {}
        nodes = _collect_nodes(verify)
        safety = _workflow_safety_summary(verify)
        verified = safety["ready_for_safe_manual_run"]
        logger.info(
            "ECOMSX222_SHOPIFY_RESULT %s",
            json.dumps({
                "ok": bool(verified),
                "workflow_id": TARGET_WORKFLOW_ID,
                "active": body.get("active"),
                "node_count": len(nodes),
                "ready_for_safe_manual_run": safety["ready_for_safe_manual_run"],
                "issues": safety["issues"],
                "nodes": [{"name": n.get("name"), "type": n.get("type"), "disabled": n.get("disabled")} for n in nodes],
                "connections": body.get("connections", {}),
                "update_result": result_payload,
            }, ensure_ascii=False, default=str)[:20000],
        )
    except Exception as exc:
        logger.exception("ECOMSX222_SHOPIFY_RESULT ok=false error=%s", type(exc).__name__)


async def maybe_inspect_ecomsx222(logger) -> None:
    await maybe_upgrade_ecomsx222_shopify(logger)

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
        safety = _workflow_safety_summary(details_payload)
        summary = {
            "ok": True,
            "workflow_id": workflow_id,
            "name": workflow.get("name") or TARGET_WORKFLOW,
            "active": body.get("active"),
            "node_count": len(nodes),
            "ready_for_safe_manual_run": safety["ready_for_safe_manual_run"],
            "issues": safety["issues"],
            "nodes": nodes,
            "connections": body.get("connections", {}),
        }
        logger.info("ECOMSX222_INSPECT_RESULT %s", json.dumps(summary, ensure_ascii=False, default=str)[:30000])
    except Exception as exc:
        logger.exception("ECOMSX222_INSPECT_RESULT ok=false error=%s", type(exc).__name__)
