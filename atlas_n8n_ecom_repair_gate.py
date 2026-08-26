"""Fail-closed gate for applying the deterministic ecomSX222 repair plan.

This module never enables itself. Live mutation requires a dedicated feature flag
plus the existing destructive n8n policy gate. It also double-checks the live
workflow fingerprint before any update to prevent TOCTOU/concurrent-change writes.
"""
from __future__ import annotations

import os
from typing import Any

from atlas_n8n import call_tool, configured
from atlas_n8n_ecom import TARGET_WORKFLOW_ID, _payload
from atlas_n8n_ecom_repair import plan_safe_ecom_repair
from atlas_n8n_ecom_run import _workflow_fingerprint
from atlas_n8n_policy import decision

REPAIR_FLAG = "N8N_APPLY_ECOMSX222_REPAIR"
UPDATE_TOOL = "update_workflow"


def _enabled(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


async def maybe_apply_safe_ecom_repair(logger) -> dict[str, Any]:
    if not _enabled(REPAIR_FLAG):
        return {"ok": False, "applied": False, "reason": "repair_flag_disabled"}
    if not configured():
        return {"ok": False, "applied": False, "reason": "n8n_not_configured"}

    allowed, reason = decision(UPDATE_TOOL, "destructive")
    if not allowed:
        return {"ok": False, "applied": False, "reason": reason}

    first = await call_tool("get_workflow_details", {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"})
    first_payload = _payload(first)
    plan = plan_safe_ecom_repair(first_payload)
    fingerprint = _workflow_fingerprint(first_payload)
    if not plan.get("ok") or not plan.get("operations") or not fingerprint:
        return {
            "ok": False,
            "applied": False,
            "reason": "repair_plan_not_applicable",
            "remaining_issues": list(plan.get("remaining_issues") or []),
        }

    second = await call_tool("get_workflow_details", {"workflowId": TARGET_WORKFLOW_ID, "detailLevel": "full"})
    second_payload = _payload(second)
    if _workflow_fingerprint(second_payload) != fingerprint:
        return {"ok": False, "applied": False, "reason": "workflow_changed_during_preflight"}

    second_plan = plan_safe_ecom_repair(second_payload)
    if second_plan.get("operations") != plan.get("operations") or not second_plan.get("ok"):
        return {"ok": False, "applied": False, "reason": "repair_plan_changed_during_preflight"}

    try:
        await call_tool(UPDATE_TOOL, {"workflowId": TARGET_WORKFLOW_ID, "operations": plan["operations"]})
    except Exception:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false reason=update_exception")
        return {
            "ok": False,
            "applied": True,
            "verified": False,
            "reason": "repair_update_exception",
        }

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

    verify_plan = plan_safe_ecom_repair(_payload(verify))
    verified = bool(verify_plan.get("ok") and not verify_plan.get("operations") and not verify_plan.get("remaining_issues"))
    if not verified:
        logger.warning("ECOMSX222_REPAIR_RESULT ok=false applied=true verified=false")
        return {"ok": False, "applied": True, "verified": False, "reason": "post_repair_verification_failed"}
    logger.info("ECOMSX222_REPAIR_RESULT ok=true applied=true verified=true")
    return {"ok": True, "applied": True, "verified": True}
