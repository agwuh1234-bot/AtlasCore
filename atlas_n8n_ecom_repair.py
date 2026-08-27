from __future__ import annotations

from typing import Any

from atlas_n8n_ecom import (
    SHOPIFY_BRIEF_NODE,
    _find_workflow_body,
    _has_connection,
    _workflow_safety_summary,
)
from atlas_n8n_graph_safety import connection_count, connection_shape_issues

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

_NODE_IDENTITY_PREFIXES = (
    "missing_node:",
    "duplicate_node_name:",
    "unexpected_node_type:",
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


def _has_node_identity_issue(issues: list[str]) -> bool:
    return any(issue.startswith(_NODE_IDENTITY_PREFIXES) for issue in issues)


def _duplicate_reviewed_edges(body: dict[str, Any]) -> list[str]:
    """Return duplicate edge issues that make a one-shot repair ambiguous."""
    issues: list[str] = []
    for source, target in (*_REQUIRED_EDGES, *_FORBIDDEN_EDGES):
        if connection_count(body, source, target) > 1:
            issues.append(f"duplicate_connection:{source}->{target}")
    return issues


def _dangling_connection_issues(body: dict[str, Any]) -> list[str]:
    """Return structural workflow issues anywhere in the graph.

    Repairs are intentionally blocked even when malformed nodes or edges sit
    outside the manual-trigger path. Writing into a structurally inconsistent
    workflow makes the outcome harder to reason about and could hide future
    activation hazards.
    """
    nodes = body.get("nodes")
    connections = body.get("connections")
    if not isinstance(nodes, list) or not isinstance(connections, dict):
        return ["malformed_workflow_graph"]

    issues: list[str] = []
    node_names: list[str] = []
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            issues.append(f"malformed_workflow_node:{index}")
            continue
        name = node.get("name")
        if not isinstance(name, str) or not name:
            issues.append(f"malformed_workflow_node_name:{index}")
            continue
        node_names.append(name)

    known_names = set(node_names)

    name_counts: dict[str, int] = {}
    for name in node_names:
        name_counts[name] = name_counts.get(name, 0) + 1
    for name, count in name_counts.items():
        if count > 1:
            issues.append(f"duplicate_workflow_node_name:{name}")

    for source, outputs in connections.items():
        if not isinstance(source, str):
            issues.append("malformed_connection_source")
            continue
        if source not in known_names:
            issues.append(f"dangling_connection_source:{source}")
        if not isinstance(outputs, dict):
            issues.append(f"malformed_connection_map:{source}")
            continue
        for output_type, branches in outputs.items():
            if not isinstance(output_type, str) or not output_type:
                issues.append(f"malformed_connection_output_type:{source}")
            elif output_type != "main":
                issues.append(f"unsupported_connection_output_type:{source}:{output_type}")
            if not isinstance(branches, list):
                issues.append(f"malformed_connection_branches:{source}")
                continue
            for branch_index, branch in enumerate(branches):
                if not isinstance(branch, list):
                    issues.append(f"malformed_connection_branch:{source}")
                    continue
                if branch_index != 0 and branch:
                    issues.append(f"unsupported_connection_branch_index:{source}:{branch_index}")
                for edge in branch:
                    if not isinstance(edge, dict):
                        issues.append(f"malformed_connection_edge:{source}")
                        continue
                    target = edge.get("node")
                    if not isinstance(target, str) or not target:
                        issues.append(f"malformed_connection_target:{source}")
                    elif target not in known_names:
                        issues.append(f"dangling_connection_target:{source}->{target}")
                    if "type" not in edge:
                        issues.append(f"missing_connection_edge_type:{source}")
                    elif not isinstance(edge.get("type"), str) or not edge.get("type"):
                        issues.append(f"malformed_connection_edge_type:{source}")
                    elif edge.get("type") != "main":
                        issues.append(f"unsupported_connection_edge_type:{source}:{edge.get('type')}")
                    if "index" not in edge:
                        issues.append(f"missing_connection_edge_index:{source}")
                    else:
                        index = edge.get("index")
                        if isinstance(index, bool) or not isinstance(index, int) or index < 0:
                            issues.append(f"malformed_connection_edge_index:{source}")

    return list(dict.fromkeys(issues))


def plan_safe_ecom_repair(value: Any) -> dict[str, Any]:
    """Return a deterministic dry-run repair plan without executing n8n writes.

    The planner only proposes narrowly reviewed topology edits. Unknown safety
    issues remain blockers and are never guessed at. If critical node identity,
    graph integrity, or reviewed edge cardinality is uncertain, no write
    operations are proposed.
    """
    body = _find_workflow_body(value)
    if not isinstance(body, dict):
        return {
            "ok": False,
            "dry_run": True,
            "operations": [],
            "remaining_issues": ["malformed_workflow_body"],
        }

    safety = _workflow_safety_summary(value)
    safety_issues = [str(issue) for issue in safety.get("issues", [])]
    if _has_node_identity_issue(safety_issues):
        return {
            "ok": False,
            "dry_run": True,
            "operations": [],
            "remaining_issues": safety_issues,
        }

    graph_issues = list(dict.fromkeys([*connection_shape_issues(body), *_dangling_connection_issues(body)]))
    if graph_issues:
        return {
            "ok": False,
            "dry_run": True,
            "operations": [],
            "remaining_issues": list(dict.fromkeys([*safety_issues, *graph_issues])),
        }

    duplicate_issues = _duplicate_reviewed_edges(body)
    if duplicate_issues:
        return {
            "ok": False,
            "dry_run": True,
            "operations": [],
            "remaining_issues": list(dict.fromkeys([*safety_issues, *duplicate_issues])),
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

    repaired_issue_keys = {
        f"unsafe_connection:{source}->{target}" for source, target in _FORBIDDEN_EDGES
    } | {
        f"missing_connection:{source}->{target}" for source, target in _REQUIRED_EDGES
    }
    planned_reachable = _planned_reachable_nodes(body, operations)

    remaining = []
    for issue in safety_issues:
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
