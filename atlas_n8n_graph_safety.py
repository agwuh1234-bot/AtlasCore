from __future__ import annotations

from typing import Any


def connection_count(body: dict[str, Any], source: str, target: str) -> int:
    """Count physical n8n edges between two named nodes."""
    connections = body.get("connections")
    if not isinstance(connections, dict):
        return 0
    outputs = connections.get(source)
    if not isinstance(outputs, dict):
        return 0

    count = 0
    for branches in outputs.values():
        if not isinstance(branches, list):
            continue
        for branch in branches:
            if not isinstance(branch, list):
                continue
            for edge in branch:
                if isinstance(edge, dict) and edge.get("node") == target:
                    count += 1
    return count


def connection_shape_issues(body: dict[str, Any]) -> list[str]:
    """Return stable fail-closed issue keys for unsupported/malformed n8n edges.

    Atlas write operations currently model only the canonical n8n connection form:
    a string source, ``main`` output type, output branch 0, string target,
    ``main`` edge type and target input index 0. Anything else is deliberately
    surfaced instead of being silently normalized or guessed at. Exact duplicate
    physical edges are also rejected globally because one-shot repair operations
    cannot safely infer which duplicate instance should be retained or removed.

    When a workflow node list is available, connection endpoints must also refer
    to real uniquely-named nodes. Duplicate node names are rejected because n8n
    connections address nodes by name, making repair targets ambiguous. Malformed
    node entries and safety-relevant node metadata are surfaced rather than
    ignored so they cannot weaken endpoint validation or silently change whether
    a node is executable.
    """
    connections = body.get("connections")
    if not isinstance(connections, dict):
        return ["malformed_connections"]

    issues: list[str] = []
    known_nodes: set[str] | None = None
    raw_nodes = body.get("nodes")
    if isinstance(raw_nodes, list):
        node_name_counts: dict[str, int] = {}
        for node_index, node in enumerate(raw_nodes):
            if not isinstance(node, dict):
                issues.append(f"malformed_workflow_node:{node_index}")
                continue
            name = node.get("name")
            if not isinstance(name, str) or not name:
                issues.append(f"malformed_workflow_node_name:{node_index}")
                continue
            node_name_counts[name] = node_name_counts.get(name, 0) + 1

            node_type = node.get("type")
            if not isinstance(node_type, str) or not node_type:
                issues.append(f"malformed_workflow_node_type:{name}")

            if "disabled" in node and not isinstance(node.get("disabled"), bool):
                issues.append(f"malformed_workflow_node_disabled:{name}")

        known_nodes = set(node_name_counts)
        for name, count in node_name_counts.items():
            if count > 1:
                issues.append(f"duplicate_workflow_node_name:{name}")

    seen_edges: set[tuple[str, str, str, int, int]] = set()
    for source, outputs in connections.items():
        if not isinstance(source, str) or not source:
            issues.append("malformed_connection_source")
            continue
        if known_nodes is not None and source not in known_nodes:
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
                    issues.append(f"malformed_connection_branch:{source}:{branch_index}")
                    continue
                if branch_index != 0 and branch:
                    issues.append(f"unsupported_connection_branch_index:{source}:{branch_index}")

                for edge_index, edge in enumerate(branch):
                    if not isinstance(edge, dict):
                        issues.append(f"malformed_connection_edge:{source}:{branch_index}:{edge_index}")
                        continue

                    unexpected_keys = sorted(str(key) for key in edge.keys() if key not in {"node", "type", "index"})
                    if unexpected_keys:
                        issues.append(
                            f"unsupported_connection_edge_metadata:{source}:{','.join(unexpected_keys)}"
                        )

                    target = edge.get("node")
                    if not isinstance(target, str) or not target:
                        issues.append(f"malformed_connection_target:{source}")
                    elif known_nodes is not None and target not in known_nodes:
                        issues.append(f"dangling_connection_target:{source}->{target}")

                    edge_type = edge.get("type")
                    if not isinstance(edge_type, str) or not edge_type:
                        issues.append(f"malformed_connection_edge_type:{source}")
                    elif edge_type != "main":
                        issues.append(f"unsupported_connection_edge_type:{source}:{edge_type}")

                    target_index = edge.get("index")
                    if isinstance(target_index, bool) or not isinstance(target_index, int) or target_index < 0:
                        issues.append(f"malformed_connection_edge_index:{source}")
                    elif target_index != 0:
                        issues.append(f"unsupported_connection_edge_index:{source}:{target_index}")

                    if (
                        isinstance(output_type, str)
                        and output_type
                        and isinstance(target, str)
                        and target
                        and isinstance(edge_type, str)
                        and edge_type
                        and isinstance(target_index, int)
                        and not isinstance(target_index, bool)
                        and target_index >= 0
                    ):
                        identity = (source, output_type, target, branch_index, target_index)
                        if identity in seen_edges:
                            issues.append(f"duplicate_physical_connection:{source}->{target}")
                        else:
                            seen_edges.add(identity)

    return list(dict.fromkeys(issues))


def duplicate_connections(body: dict[str, Any], watched_edges: tuple[tuple[str, str], ...]) -> list[str]:
    """Return stable issue keys for watched edges that occur more than once."""
    issues: list[str] = []
    for source, target in watched_edges:
        if connection_count(body, source, target) > 1:
            issues.append(f"duplicate_connection:{source}->{target}")
    return issues
