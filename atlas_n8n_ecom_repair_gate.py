"""Fail-closed gate for applying the deterministic ecomSX222 repair plan.

This module never enables itself. Live mutation requires a dedicated feature flag
plus the existing destructive n8n policy gate. It also double-checks the live
workflow fingerprint before any update to prevent TOCTOU/concurrent-change writes.
Repairs are allowed only while the target workflow is explicitly inactive.
"""
from __future__ import annotations

import os
from typing import Any

from atlas_n8n import call_tool, configured
from atlas_n8n_ecom import TARGET_WORKFLOW_ID, _find_workflow_body, _payload
from atlas_n8n_ecom_repair import plan_safe_ecom_repair
from atlas_n8n_ecom_run import _workflow_fingerprint
from atlas_n8n_policy import decision

REPAIR_FLAG = "N8N_APPLY_ECOMSX222_REPAIR"
UPDATE_TOOL = "update_workflow"


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _explicitly_inactive(value: Any) -> bool:
    body = _find_workflow_body(value)
    return isinstance(body, dict) and body.get("active") is False


def _tool_call_reported_error(value: Any) -> bool:
    """Recognize MCP tool errors whether returned as an object or plain mapping."""
    if isinstance(value, dict):
        return value.get("isError") is True or value.get("is_error") is True
    return getattr(value, "isError", False) is True or getattr(value, "is_error", False) is True


def _repair_state_verified(payload: Any, original_fingerprint: str) -> tuple[bool, str]:
    if not _explicitly_inactive(payload):
        return False, "active_or_unknown"
    fingerprint = _workflow_fingerprint(payload)
    if not fingerprint:
        return False, "missing_fingerprint"
    if fingerprint == original_fingerprint:
        return False, "unchanged"
    plan = plan_safe_ecom_repair(payload)
    if not (plan.get("ok") and not plan.get("operations") and not plan.get("remaining_issues")):
        return False, "repair_not_verified"
    return True, fingerprint


async def _reconcile_ambiguous_update(logger, original_fingerprint: str, reason: str) -> dict[str, Any]:
    """Read back twice after an ambiguous write without issuing another mutation."""
    try:
        first = await call_tool("get_workflow_details", {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"})
    except Exception:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=%s_reconciliation_read_exception", reason)
        return {"ok": False, "applied": True, "verified": False, "reason": reason}

    if _tool_call_reported_error(first):
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=%s_reconciliation_read_tool_error", reason)
        return {"ok": False, "applied": True, "verified": False, "reason": reason}

    first_payload = _payload(first)
    first_ok, first_state = _repair_state_verified(first_payload, original_fingerprint)
    if not first_ok:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=%s_reconciliation_%s", reason, first_state)
        return {"ok": False, "applied": True, "verified": False, "reason": reason}

    try:
        second = await call_tool("get_workflow_details", {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"})
    except Exception:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=%s_reconciliation_second_read_exception", reason)
        return {"ok": False, "applied": True, "verified": False, "reason": reason}

    if _tool_call_reported_error(second):
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=%s_reconciliation_second_read_tool_error", reason)
        return {"ok": False, "applied": True, "verified": False, "reason": reason}

    second_payload = _payload(second)
    second_ok, second_state = _repair_state_verified(second_payload, original_fingerprint)
    if not second_ok:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=%s_reconciliation_second_%s", reason, second_state)
        return {"ok": False, "applied": True, "verified": False, "reason": reason}
    if second_state != first_state:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=%s_reconciliation_changed", reason)
        return {"ok": False, "applied": True, "verified": False, "reason": reason}

    logger.info("ECOMSX222_REPAIR_RESULT ok=true applied=true verified=true reconciled=true stable=true")
    return {"ok": True, "applied": True, "verified": True, "reconciled": True}


async def maybe_apply_safe_ecom_repair(logger) -> dict[str, Any]:
    if not _enabled(REPAIR_FLAG):
        return {"ok": False, "applied": False, "reason": "repair_flag_disabled"}
    if not configured():
        return {"ok": False, "applied": False, "reason": "n8n_not_configured"}

    allowed, reason = decision(UPDATE_TOOL, "destructive")
    if not allowed:
        return {"ok": False, "applied": False, "reason": reason}

    try:
        first = await call_tool("get_workflow_details", {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"})
    except Exception:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=false reason=preflight_first_read_exception")
        return {"ok": False, "applied": False, "reason": "preflight_first_read_exception"}

    if _tool_call_reported_error(first):
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=false reason=preflight_first_read_tool_error")
        return {"ok": False, "applied": False, "reason": "preflight_first_read_tool_error"}

    first_payload = _payload(first)
    if not _explicitly_inactive(first_payload):
        return {"ok": False, "applied": False, "reason": "workflow_not_explicitly_inactive"}

    plan = plan_safe_ecom_repair(first_payload)
    fingerprint = _workflow_fingerprint(first_payload)
    if not plan.get("ok") or not plan.get("operations") or not fingerprint:
        return {
            "ok": False,
            "applied": False,
            "reason": "repair_plan_not_applicable",
            "remaining_issues": list(plan.get("remaining_issues") or []),
        }

    try:
        second = await call_tool("get_workflow_details", {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"})
    except Exception:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=false reason=preflight_second_read_exception")
        return {"ok": False, "applied": False, "reason": "preflight_second_read_exception"}

    if _tool_call_reported_error(second):
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=false reason=preflight_second_read_tool_error")
        return {"ok": False, "applied": False, "reason": "preflight_second_read_tool_error"}

    second_payload = _payload(second)
    if not _explicitly_inactive(second_payload):
        return {"ok": False, "applied": False, "reason": "workflow_became_active_during_preflight"}
    if _workflow_fingerprint(second_payload) != fingerprint:
        return {"ok": False, "applied": False, "reason": "workflow_changed_during_preflight"}

    second_plan = plan_safe_ecom_repair(second_payload)
    if second_plan.get("operations") != plan.get("operations") or not second_plan.get("ok"):
        return {"ok": False, "applied": False, "reason": "repair_plan_changed_during_preflight"}

    try:
        update_result = await call_tool(UPDATE_TOOL, {"workflowId": TARGET_WORKFLOW_ID, "operations": plan["operations"]})
    except Exception:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=update_exception")
        return await _reconcile_ambiguous_update(logger, fingerprint, "repair_update_exception")

    if _tool_call_reported_error(update_result):
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=update_tool_reported_error")
        return await _reconcile_ambiguous_update(logger, fingerprint, "repair_update_tool_error")

    try:
        verify = await call_tool("get_workflow_details", {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"})
    except Exception:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=verification_read_exception")
        return {
            "ok": False,
            "applied": True,
            "verified": False,
            "reason": "post_repair_verification_exception",
        }

    if _tool_call_reported_error(verify):
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=verification_read_tool_error")
        return {
            "ok": False,
            "applied": True,
            "verified": False,
            "reason": "post_repair_verification_tool_error",
        }

    verify_payload = _payload(verify)
    if not _explicitly_inactive(verify_payload):
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=workflow_active_after_repair")
        return {
            "ok": False,
            "applied": True,
            "verified": False,
            "reason": "workflow_active_after_repair",
        }

    verify_fingerprint = _workflow_fingerprint(verify_payload)
    if not verify_fingerprint or verify_fingerprint == fingerprint:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=workflow_unchanged_after_repair")
        return {
            "ok": False,
            "applied": True,
            "verified": False,
            "reason": "workflow_unchanged_after_repair",
        }

    verify_plan = plan_safe_ecom_repair(verify_payload)
    verified = bool(verify_plan.get("ok") and not verify_plan.get("operations") and not verify_plan.get("remaining_issues"))
    if not verified:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false")
        return {"ok": False, "applied": True, "verified": False, "reason": "post_repair_verification_failed"}
    logger.info("ECOMSX222_REPAIR_RESULT ok=true applied=true verified=true")
    return {"ok": True, "applied": True, "verified": True}
