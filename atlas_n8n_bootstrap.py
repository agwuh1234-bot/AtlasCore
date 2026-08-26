from __future__ import annotations

import json
import os
from typing import Any

from atlas_n8n import call_tool, configured
from atlas_n8n_policy import decision

WORKFLOW_NAME = "Atlas ChatGPT Access Test"

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
            logger.info(
                "N8N_BOOTSTRAP_RESULT ok=true action=existing workflow_id=%s name=%s",
                workflow_id,
                WORKFLOW_NAME,
            )
            return

        validation = await call_tool("validate_workflow", {"code": WORKFLOW_CODE})
        validation_payload = _extract_json_payload(validation)
        valid = isinstance(validation_payload, dict) and validation_payload.get("valid") is True
        if not valid:
            logger.warning(
                "N8N_BOOTSTRAP_RESULT ok=false error=validation_failed payload=%s",
                json.dumps(validation_payload, ensure_ascii=False, default=str)[:2500],
            )
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
        workflow_id = None
        if isinstance(created_payload, dict):
            workflow_id = created_payload.get("workflowId") or created_payload.get("id")

        verify = await call_tool("search_workflows", {"query": WORKFLOW_NAME, "limit": 50})
        verified = _find_named_workflow(_extract_json_payload(verify), WORKFLOW_NAME)
        verified_id = None
        if verified:
            verified_id = verified.get("id") or verified.get("workflowId")

        if verified_id:
            logger.info(
                "N8N_BOOTSTRAP_RESULT ok=true action=created workflow_id=%s name=%s verified=true",
                verified_id,
                WORKFLOW_NAME,
            )
        else:
            logger.warning(
                "N8N_BOOTSTRAP_RESULT ok=false error=verification_failed created_workflow_id=%s",
                workflow_id,
            )
    except Exception as exc:
        logger.exception("N8N_BOOTSTRAP_RESULT ok=false error=%s", type(exc).__name__)
