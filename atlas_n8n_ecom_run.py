"""Fail-closed execution gate for the ecomSX222 n8n workflow.

The gate re-fetches the live workflow immediately before execution and refuses to
run unless the topology is still safe, the workflow is inactive, and a dedicated
feature flag is enabled. The underlying n8n bridge/policy still performs its own
live discovery and write-policy checks before any execution tool call.
"""

from __future__ import annotations

import hashlib
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


def _workflow_fingerprint(details_payload: Any) -> str | None:
    """Return a stable digest of the live workflow body without logging content."""
    body = _find_workflow_body(details_payload)
    if not isinstance(body, dict):
        return None
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _receipt_identifier(value: Any) -> str | None:
    """Normalize only scalar receipt identifiers; reject containers and booleans."""
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, (str, int)):
        return None
    normalized = str(value).strip()
    if not normalized or len(normalized) > 256:
        return None
    return normalized


def _execution_receipt(payload: Any, expected_workflow_id: str = TARGET_WORKFLOW_ID) -> dict[str, Any]:
    """Extract only non-sensitive confirmation that n8n accepted an execution.

    An execution identifier alone is not sufficient if n8n also reports an
    explicit failure or unknown state. Explicit statuses are fail-closed: only
    known accepted states confirm execution. If n8n returns a workflow id, it
    must match the workflow that Atlas requested; a mismatched receipt is never
    treated as success. Container/boolean identifier values are rejected so a
    malformed MCP payload cannot masquerade as a valid receipt. When status and
    workflow id are absent, a valid scalar execution identifier is accepted as
    the minimal receipt.
    """
    if not isinstance(payload, dict):
        return {
            "confirmed": False,
            "execution_id_present": False,
            "status": None,
            "workflow_id_present": False,
            "workflow_id_matches": None,
        }

    execution_id = _receipt_identifier(
        payload.get("executionId") or payload.get("execution_id") or payload.get("id")
    )
    status = payload.get("status")
    if isinstance(status, str):
        status = status.strip().lower() or None
    else:
        status = None

    raw_workflow_id = payload.get("workflowId") or payload.get("workflow_id")
    receipt_workflow_id = _receipt_identifier(raw_workflow_id)
    workflow_id_present = raw_workflow_id is not None
    workflow_id_matches = None
    if workflow_id_present:
        workflow_id_matches = (
            receipt_workflow_id is not None
            and receipt_workflow_id == str(expected_workflow_id)
        )

    accepted_statuses = {"running", "success", "completed", "queued", "waiting"}
    failed_statuses = {"failed", "error", "cancelled", "canceled", "crashed", "stopped"}
    if workflow_id_matches is False:
        confirmed = False
    elif status in failed_statuses:
        confirmed = False
    elif status is not None:
        confirmed = status in accepted_statuses
    else:
        confirmed = bool(execution_id)
    return {
        "confirmed": confirmed,
        "execution_id_present": bool(execution_id),
        "status": status,
        "workflow_id_present": workflow_id_present,
        "workflow_id_matches": workflow_id_matches,
    }


def execution_readiness(details_payload: Any) -> dict[str, Any]:
    """Return a side-effect-free decision for whether ecomSX222 is safe to run."""
    body = _find_workflow_body(details_payload) or {}
    safety = _workflow_safety_summary(details_payload)
    issues = list(safety.get("issues") or [])

    if body.get("active") is True:
        issues.append("workflow_active")

    return {
        "ready": not issues,
        "workflow_id": TARGET_WORKFLOW_ID,
        "active": body.get("active"),
        "issues": issues,
    }


async def maybe_run_ecomsx222_safe(logger) -> dict[str, Any]:
    """Execute ecomSX222 only after a fresh safety check and explicit opt-in."""
    if not _enabled(RUN_FLAG):
        return {"ok": False, "executed": False, "reason": "run_flag_disabled"}

    if not configured():
        logger.warning("ECOMSX222_RUN_RESULT ok=false executed=false reason=n8n_not_configured")
        return {"ok": False, "executed": False, "reason": "n8n_not_configured"}

    allowed, reason = decision(EXECUTE_TOOL, "write")
    if not allowed:
        logger.warning("ECOMSX222_RUN_RESULT ok=false executed=false reason=%s", reason)
        return {"ok": False, "executed": False, "reason": reason}

    execution_attempted = False
    try:
        details = await call_tool(
            "get_workflow_details",
            {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"},
        )
        details_payload = _payload(details)
        readiness = execution_readiness(details_payload)
        first_fingerprint = _workflow_fingerprint(details_payload)
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

        confirm = await call_tool(
            "get_workflow_details",
            {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"},
        )
        confirm_payload = _payload(confirm)
        confirm_readiness = execution_readiness(confirm_payload)
        second_fingerprint = _workflow_fingerprint(confirm_payload)
        if (
            not first_fingerprint
            or not second_fingerprint
            or first_fingerprint != second_fingerprint
            or not confirm_readiness["ready"]
        ):
            issues = list(confirm_readiness.get("issues") or [])
            if first_fingerprint != second_fingerprint:
                issues.append("workflow_changed_during_preflight")
            if not first_fingerprint or not second_fingerprint:
                issues.append("workflow_fingerprint_unavailable")
            logger.warning(
                "ECOMSX222_RUN_RESULT %s",
                json.dumps(
                    {
                        "ok": False,
                        "executed": False,
                        "reason": "preflight_changed",
                        "workflow_id": TARGET_WORKFLOW_ID,
                        "issues": issues,
                    },
                    ensure_ascii=False,
                ),
            )
            return {
                "ok": False,
                "executed": False,
                "reason": "preflight_changed",
                "issues": issues,
            }

        execution_attempted = True
        result = await call_tool(EXECUTE_TOOL, {"workflowId": TARGET_WORKFLOW_ID})
        payload = _payload(result)
        receipt = _execution_receipt(payload)
        if not receipt["confirmed"]:
            logger.warning(
                "ECOMSX222_RUN_RESULT %s",
                json.dumps(
                    {
                        "ok": False,
                        "executed": True,
                        "reason": "execution_result_unconfirmed",
                        "workflow_id": TARGET_WORKFLOW_ID,
                        "status": receipt["status"],
                        "receipt_workflow_id_present": receipt["workflow_id_present"],
                        "receipt_workflow_id_matches": receipt["workflow_id_matches"],
                    },
                    ensure_ascii=False,
                ),
            )
            return {
                "ok": False,
                "executed": True,
                "reason": "execution_result_unconfirmed",
                "workflow_id": TARGET_WORKFLOW_ID,
                "status": receipt["status"],
            }

        logger.info(
            "ECOMSX222_RUN_RESULT %s",
            json.dumps(
                {
                    "ok": True,
                    "executed": True,
                    "workflow_id": TARGET_WORKFLOW_ID,
                    "execution_id_present": receipt["execution_id_present"],
                    "status": receipt["status"],
                    "receipt_workflow_id_present": receipt["workflow_id_present"],
                    "receipt_workflow_id_matches": receipt["workflow_id_matches"],
                },
                ensure_ascii=False,
            ),
        )
        return {"ok": True, "executed": True, "workflow_id": TARGET_WORKFLOW_ID}
    except Exception as exc:
        logger.exception(
            "ECOMSX222_RUN_RESULT ok=false executed=%s error=%s",
            str(execution_attempted).lower(),
            type(exc).__name__,
        )
        return {
            "ok": False,
            "executed": execution_attempted,
            "reason": "execution_exception" if execution_attempted else type(exc).__name__,
        }
