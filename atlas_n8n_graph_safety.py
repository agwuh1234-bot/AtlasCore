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


def duplicate_connections(body: dict[str, Any], watched_edges: tuple[tuple[str, str], ...]) -> list[str]:
    """Return stable issue keys for watched edges that occur more than once."""
    issues: list[str] = []
    for source, target in watched_edges:
        if connection_count(body, source, target) > 1:
            issues.append(f"duplicate_connection:{source}->{target}")
    return issues
