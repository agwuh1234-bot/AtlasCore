"""Fail-closed execution gate for the ecomSX222 n8n workflow.

The gate re-fetches the live workflow immediately before execution and refuses to
run unless the topology is still safe, the workflow is inactive, and a dedicated
feature flag is enabled. The underlying n8n bridge/policy still performs its own
live discovery and write-policy checks before any execution tool call.
"""

from __future__ import annotations

import json
import os
from typing import Any

from atlas_n8n import call_tool, configured
from atlas_n8n_ecom import TARGET_WORKFLOW_ID, _find_workflow_body, _payload, _workflow_safety_summary
from atlas_n8n_policy import decision

RUN_FLAG = "N8N_RUN_ECOMSX222_SAFE"
EXECUTE_TOOL = "execute_workflow"


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def execution_readiness(details_payload: Any) -> dict[str, Any]:
    """Return a side-effect-free decision for whether ecomSX222 is safe to run."""
    body = _find_workflow_body(details_payload) or {}
    safety = _workflow_safety_summary(details_payload)
    issues = list(safety.get("issues") or [])

    # Keep the workflow manual-only. An active workflow could be triggered by an
    # external event while Atlas is inspecting/running it, so fail closed.
    if body.get("active") is True:
        issues.append("workflow_active")

    return {
        "ready": not issues,
        "workflow_id": TARGET_WORKFLOW_ID,
        "active": body.get("active"),
        "issues": issues,
    }


async def maybe_run_ecomsx222_safe(logger) -> dict[str, Any]:
    """Execute ecomSX222 only after a fresh safety check and explicit opt-in.

    This function intentionally does nothing when RUN_FLAG is off. Execution is
    also blocked if n8n is unavailable, write policy is disabled, or the live
    workflow no longer matches the known-safe manual topology.
    """
    if not _enabled(RUN_FLAG):
        return {"ok": False, "executed": False, "reason": "run_flag_disabled"}

    if not configured():
        logger.warning("ECOMSX222_RUN_RESULT ok=false executed=false reason=n8n_not_configured")
        return {"ok": False, "executed": False, "reason": "n8n_not_configured"}

    allowed, reason = decision(EXECUTE_TOOL, "write")
    if not allowed:
        logger.warning("ECOMSX222_RUN_RESULT ok=false executed=false reason=%s", reason)
        return {"ok": False, "executed": False, "reason": reason}

    try:
        details = await call_tool(
            "get_workflow_details",
            {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"},
        )
        details_payload = _payload(details)
        readiness = execution_readiness(details_payload)
        if not readiness["ready"]:
            logger.warning(
                "ECOMSX222_RUN_RESULT %s",
                json.dumps(
                    {
                        "ok": False,
                        "executed": False,
                        "reason": "safety_check_failed",
                        "workflow_id": TARGET_WORKFLOW_ID,
                        "issues": readiness["issues"],
                    },
                    ensure_ascii=False,
                ),
            )
            return {
                "ok": False,
                "executed": False,
                "reason": "safety_check_failed",
                "issues": readiness["issues"],
            }

        result = await call_tool(EXECUTE_TOOL, {"workflowId": TARGET_WORKFLOW_ID})
        payload = _payload(result)
        logger.info(
            "ECOMSX222_RUN_RESULT %s",
            json.dumps(
                {
                    "ok": True,
                    "executed": True,
                    "workflow_id": TARGET_WORKFLOW_ID,
                    "result_present": payload is not None,
                },
                ensure_ascii=False,
            ),
        )
        return {"ok": True, "executed": True, "workflow_id": TARGET_WORKFLOW_ID}
    except Exception as exc:
        logger.exception("ECOMSX222_RUN_RESULT ok=false executed=false error=%s", type(exc).__name__)
        return {"ok": False, "executed": False, "reason": type(exc).__name__}
