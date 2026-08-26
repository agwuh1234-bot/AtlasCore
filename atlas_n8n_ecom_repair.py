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


def _connection_targets(connections: Any) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    if not isinstance(connections, dict):
        return graph

    for source, outputs in connections.items():
        if not isinstance(source, str) or not isinstance(outputs, dict):
            continue
        for branches in outputs.values():
            if not isinstance(branches, list):
                continue
            for branch in branches:
                if not isinstance(branch, list):
                    continue
                for edge in branch:
                    if not isinstance(edge, dict):
                        continue
                    target = edge.get("node")
                    if isinstance(target, str):
                        graph.setdefault(source, set()).add(target)
    return graph


def _planned_graph(body: dict[str, Any], operations: list[dict[str, Any]]) -> dict[str, set[str]]:
    graph = _connection_targets(body.get("connections"))

    for operation in operations:
        source = operation.get("source")
        target = operation.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        if operation.get("type") == "removeConnection":
            graph.setdefault(source, set()).discard(target)
        elif operation.get("type") == "addConnection":
            graph.setdefault(source, set()).add(target)
    return graph


def _planned_reachable_nodes(body: dict[str, Any], operations: list[dict[str, Any]]) -> set[str]:
    graph = _planned_graph(body, operations)
    reachable: set[str] = set()
    stack = [TRIGGER_NODE]
    while stack:
        current = stack.pop()
        if current in reachable:
            continue
        reachable.add(current)
        stack.extend(graph.get(current, ()))
    return reachable


def _planned_reachable_cycle(body: dict[str, Any], operations: list[dict[str, Any]]) -> bool:
    """Return True when the planned graph has a cycle reachable from the manual trigger."""
    graph = _planned_graph(body, operations)
    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> bool:
        if node in active:
            return True
        if node in visited:
            return False
        visited.add(node)
        active.add(node)
        for target in graph.get(node, ()):
            if visit(target):
                return True
        active.remove(node)
        return False

    return visit(TRIGGER_NODE)


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
    planned_reachable = _planned_reachable_nodes(body, operations)

    remaining = []
    for issue in safety.get("issues", []):
        if issue in repaired_issue_keys:
            continue
        if issue.startswith("unexpected_reachable_node:"):
            node_name = issue.split(":", 1)[1]
            if node_name not in planned_reachable:
                continue
        remaining.append(issue)

    if _planned_reachable_cycle(body, operations):
        remaining.append("reachable_cycle")

    return {
        "ok": not remaining,
        "dry_run": True,
        "operations": operations,
        "remaining_issues": remaining,
    }
