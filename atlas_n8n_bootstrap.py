from __future__ import annotations

import json
import os
from typing import Any

from atlas_n8n import call_tool, configured
from atlas_n8n_policy import decision

WORKFLOW_NAME = "Atlas ChatGPT Access Test"
WORKFLOW_ID = "IHegwc8h7cZBWOaZ"
SECOND_NODE_NAME = "Atlas Second Node"
PING_NODE_NAME = "Atlas Ping"

WORKFLOW_CODE = r"""
import { workflow, trigger, node } from '@n8n/workflow-sdk';

const manualTrigger = trigger({
  type: 'n8n-nodes-base.manualTrigger',
  version: 1,
  config: { name: 'Manual Trigger' },
});

const setNode = node({
  type: 'n8n-nodes-base.set',
  version: 3.4,
  config: {
    name: 'Atlas Set Test',
    parameters: {
      assignments: {
        assignments: [
          { id: 'atlas-message', name: 'message', value: 'Atlas n8n bridge OK', type: 'string' },
        ],
      },
    },
  },
});

export default workflow('atlas-chatgpt-access-test', 'Atlas ChatGPT Access Test')
  .add(manualTrigger)
  .to(setNode);
""".strip()


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _extract_json_payload(result: Any) -> Any:
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


def _find_named_workflow(value: Any, name: str) -> dict | None:
    if isinstance(value, dict):
        if value.get("name") == name and (value.get("id") or value.get("workflowId")):
            return value
        for child in value.values():
            found = _find_named_workflow(child, name)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_named_workflow(child, name)
            if found:
                return found
    return None


def _contains_node(value: Any, node_name: str) -> bool:
    if isinstance(value, dict):
        if value.get("name") == node_name and (value.get("type") or value.get("typeVersion") or value.get("parameters") is not None):
            return True
        return any(_contains_node(child, node_name) for child in value.values())
    if isinstance(value, list):
        return any(_contains_node(child, node_name) for child in value)
    return False


async def maybe_bootstrap_test_workflow(logger) -> None:
    if not _enabled("N8N_BOOTSTRAP_TEST_WORKFLOW"):
        return
    if not configured():
        logger.warning("N8N_BOOTSTRAP_RESULT ok=false error=n8n_not_configured")
        return

    allowed, reason = decision("create_workflow_from_code", "write")
    if not allowed:
        logger.warning("N8N_BOOTSTRAP_RESULT ok=false error=policy_blocked reason=%s", reason)
        return

    try:
        search = await call_tool("search_workflows", {"query": WORKFLOW_NAME, "limit": 50})
        existing = _find_named_workflow(_extract_json_payload(search), WORKFLOW_NAME)
        if existing:
            workflow_id = existing.get("id") or existing.get("workflowId")
            logger.info("N8N_BOOTSTRAP_RESULT ok=true action=existing workflow_id=%s name=%s", workflow_id, WORKFLOW_NAME)
            return

        validation = await call_tool("validate_workflow", {"code": WORKFLOW_CODE})
        validation_payload = _extract_json_payload(validation)
        valid = isinstance(validation_payload, dict) and validation_payload.get("valid") is True
        if not valid:
            logger.warning("N8N_BOOTSTRAP_RESULT ok=false error=validation_failed payload=%s", json.dumps(validation_payload, ensure_ascii=False, default=str)[:2500])
            return

        created = await call_tool(
            "create_workflow_from_code",
            {
                "code": WORKFLOW_CODE,
                "name": WORKFLOW_NAME,
                "description": "Created by Atlas to verify secure ChatGPT-to-n8n workflow write access.",
                "versionName": "Initial Atlas bridge test",
                "versionDescription": "Manual Trigger connected to an Edit Fields/Set node for bridge verification.",
            },
        )
        created_payload = _extract_json_payload(created)
        workflow_id = created_payload.get("workflowId") if isinstance(created_payload, dict) else None

        verify = await call_tool("search_workflows", {"query": WORKFLOW_NAME, "limit": 50})
        verified = _find_named_workflow(_extract_json_payload(verify), WORKFLOW_NAME)
        verified_id = (verified.get("id") or verified.get("workflowId")) if verified else None
        if verified_id:
            logger.info("N8N_BOOTSTRAP_RESULT ok=true action=created workflow_id=%s name=%s verified=true", verified_id, WORKFLOW_NAME)
        else:
            logger.warning("N8N_BOOTSTRAP_RESULT ok=false error=verification_failed created_workflow_id=%s", workflow_id)
    except Exception as exc:
        logger.exception("N8N_BOOTSTRAP_RESULT ok=false error=%s", type(exc).__name__)


async def maybe_add_second_test_node(logger) -> None:
    if not _enabled("N8N_BOOTSTRAP_SECOND_NODE"):
        return
    if not configured():
        logger.warning("N8N_SECOND_NODE_RESULT ok=false error=n8n_not_configured")
        return

    allowed, reason = decision("update_workflow", "write")
    if not allowed:
        logger.warning("N8N_SECOND_NODE_RESULT ok=false error=policy_blocked reason=%s", reason)
        return

    try:
        details = await call_tool("get_workflow_details", {"workflowId": WORKFLOW_ID, "detailLevel": "full"})
        details_payload = _extract_json_payload(details)
        if _contains_node(details_payload, SECOND_NODE_NAME):
            logger.info("N8N_SECOND_NODE_RESULT ok=true action=existing workflow_id=%s node=%s verified=true", WORKFLOW_ID, SECOND_NODE_NAME)
            return

        node_parameters = {
            "assignments": {
                "assignments": [
                    {"id": "atlas-second", "name": "second", "value": "node created", "type": "string"}
                ]
            }
        }
        validation = await call_tool(
            "validate_node_config",
            {"nodes": [{"name": SECOND_NODE_NAME, "type": "n8n-nodes-base.set", "typeVersion": 3.4, "parameters": node_parameters}]},
        )
        validation_payload = _extract_json_payload(validation)
        if isinstance(validation_payload, dict) and validation_payload.get("valid") is False:
            logger.warning("N8N_SECOND_NODE_RESULT ok=false error=node_validation_failed payload=%s", json.dumps(validation_payload, ensure_ascii=False, default=str)[:2000])
            return

        result = await call_tool(
            "update_workflow",
            {
                "workflowId": WORKFLOW_ID,
                "operations": [
                    {
                        "type": "addNode",
                        "node": {
                            "name": SECOND_NODE_NAME,
                            "type": "n8n-nodes-base.set",
                            "typeVersion": 3.4,
                            "parameters": node_parameters,
                            "position": [700, 300],
                        },
                    },
                    {"type": "addConnection", "source": "Atlas Set Test", "target": SECOND_NODE_NAME},
                ],
            },
        )
        result_payload = _extract_json_payload(result)

        verify = await call_tool("get_workflow_details", {"workflowId": WORKFLOW_ID, "detailLevel": "full"})
        verified = _contains_node(_extract_json_payload(verify), SECOND_NODE_NAME)
        if verified:
            node_count = result_payload.get("nodeCount") if isinstance(result_payload, dict) else None
            logger.info("N8N_SECOND_NODE_RESULT ok=true action=created workflow_id=%s node=%s node_count=%s verified=true", WORKFLOW_ID, SECOND_NODE_NAME, node_count)
        else:
            logger.warning("N8N_SECOND_NODE_RESULT ok=false error=verification_failed workflow_id=%s node=%s", WORKFLOW_ID, SECOND_NODE_NAME)
    except Exception as exc:
        logger.exception("N8N_SECOND_NODE_RESULT ok=false error=%s", type(exc).__name__)


async def maybe_add_ping_node(logger) -> None:
    if not _enabled("N8N_BOOTSTRAP_PING_NODE"):
        return
    if not configured():
        logger.warning("N8N_PING_NODE_RESULT ok=false error=n8n_not_configured")
        return

    allowed, reason = decision("update_workflow", "write")
    if not allowed:
        logger.warning("N8N_PING_NODE_RESULT ok=false error=policy_blocked reason=%s", reason)
        return

    try:
        details = await call_tool("get_workflow_details", {"workflowId": WORKFLOW_ID, "detailLevel": "full"})
        details_payload = _extract_json_payload(details)
        if _contains_node(details_payload, PING_NODE_NAME):
            logger.info("N8N_PING_NODE_RESULT ok=true action=existing workflow_id=%s node=%s verified=true", WORKFLOW_ID, PING_NODE_NAME)
            return

        node_parameters = {
            "assignments": {
                "assignments": [
                    {"id": "atlas-ping", "name": "ping", "value": "pong", "type": "string"},
                    {"id": "atlas-status", "name": "status", "value": "n8n write access confirmed", "type": "string"}
                ]
            }
        }
        result = await call_tool(
            "update_workflow",
            {
                "workflowId": WORKFLOW_ID,
                "operations": [
                    {
                        "type": "addNode",
                        "node": {
                            "name": PING_NODE_NAME,
                            "type": "n8n-nodes-base.set",
                            "typeVersion": 3.4,
                            "parameters": node_parameters,
                            "position": [950, 300],
                        },
                    },
                    {"type": "addConnection", "source": SECOND_NODE_NAME, "target": PING_NODE_NAME},
                ],
            },
        )
        result_payload = _extract_json_payload(result)
        verify = await call_tool("get_workflow_details", {"workflowId": WORKFLOW_ID, "detailLevel": "full"})
        verified = _contains_node(_extract_json_payload(verify), PING_NODE_NAME)
        if verified:
            node_count = result_payload.get("nodeCount") if isinstance(result_payload, dict) else None
            logger.info("N8N_PING_NODE_RESULT ok=true action=created workflow_id=%s node=%s node_count=%s verified=true", WORKFLOW_ID, PING_NODE_NAME, node_count)
        else:
            logger.warning("N8N_PING_NODE_RESULT ok=false error=verification_failed workflow_id=%s node=%s", WORKFLOW_ID, PING_NODE_NAME)
    except Exception as exc:
        logger.exception("N8N_PING_NODE_RESULT ok=false error=%s", type(exc).__name__)
