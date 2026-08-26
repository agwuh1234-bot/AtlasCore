from __future__ import annotations

from typing import Any

from atlas_n8n_ecom import (
    SHOPIFY_BRIEF_NODE,
    _find_workflow_body,
    _has_connection,
    _workflow_safety_summary,
)

TRIGGER_NODE = "When clicking ‘Execute workflow’"

_REQUIRED_EDGES = (
    (TRIGGER_NODE, SHOPIFY_BRIEF_NODE),
    (SHOPIFY_BRIEF_NODE, "Message a model1"),
    ("Message a model1", "Message a model"),
)

_FORBIDDEN_EDGES = (
    (TRIGGER_NODE, "HTTP Request"),
    ("HTTP Request", "Message a model1"),
    ("Message a model", "Edit a file"),
)


def plan_safe_ecom_repair(value: Any) -> dict[str, Any]:
    """Return a deterministic dry-run repair plan without executing n8n writes.

    The planner only proposes narrowly reviewed topology edits. Unknown safety
    issues remain blockers and are never guessed at.
    """
    body = _find_workflow_body(value)
    if not isinstance(body, dict):
        return {
            "ok": False,
            "dry_run": True,
            "operations": [],
            "remaining_issues": ["malformed_workflow_body"],
        }

    operations: list[dict[str, Any]] = []

    for source, target in _FORBIDDEN_EDGES:
        if _has_connection(body, source, target):
            operations.append(
                {
                    "type": "removeConnection",
                    "source": source,
                    "target": target,
                    "ignoreErrors": False,
                }
            )

    for source, target in _REQUIRED_EDGES:
        if not _has_connection(body, source, target):
            operations.append(
                {
                    "type": "addConnection",
                    "source": source,
                    "target": target,
                }
            )

    safety = _workflow_safety_summary(value)
    repaired_issue_keys = {
        f"unsafe_connection:{source}->{target}" for source, target in _FORBIDDEN_EDGES
    } | {
        f"missing_connection:{source}->{target}" for source, target in _REQUIRED_EDGES
    }

    remaining = [
        issue
        for issue in safety.get("issues", [])
        if issue not in repaired_issue_keys
        and not (
            issue.startswith("unexpected_reachable_node:")
            and any(op["type"] == "removeConnection" for op in operations)
        )
    ]

    return {
        "ok": not remaining,
        "dry_run": True,
        "operations": operations,
        "remaining_issues": remaining,
    }
