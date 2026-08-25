from __future__ import annotations

import json
import time
from typing import Any

from atlas_store import AtlasStore


class AtlasAutonomyStore:
    """Durable checkpoint adapter using AtlasStore's configured database."""

    def __init__(self, store: AtlasStore) -> None:
        self.store = store
        self._initialize()

    def _initialize(self) -> None:
        with self.store._connection(immediate=True) as conn:
            self.store._execute(conn, """
                CREATE TABLE IF NOT EXISTS atlas_autonomous_tasks (
                    id TEXT PRIMARY KEY,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    created_at DOUBLE PRECISION NOT NULL,
                    updated_at DOUBLE PRECISION NOT NULL
                )
            """)
            self.store._execute(conn,
                "CREATE INDEX IF NOT EXISTS atlas_autonomous_status_idx ON atlas_autonomous_tasks(status, updated_at)")

    def save(self, task: dict[str, Any]) -> None:
        if not task or not task.get("id"):
            return
        now = time.time()
        created = float(task.get("created_at") or now)
        payload = json.dumps(task, ensure_ascii=False, separators=(",", ":"))
        with self.store._connection(immediate=True) as conn:
            self.store._execute(conn, """
                INSERT INTO atlas_autonomous_tasks(id, goal, status, snapshot_json, created_at, updated_at)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    goal = excluded.goal,
                    status = excluded.status,
                    snapshot_json = excluded.snapshot_json,
                    updated_at = excluded.updated_at
            """, (str(task["id"]), str(task.get("goal") or ""), str(task.get("status") or "queued"), payload, created, now))

    def load_active(self) -> list[dict[str, Any]]:
        with self.store._connection() as conn:
            rows = self.store._execute(conn, """
                SELECT snapshot_json FROM atlas_autonomous_tasks
                WHERE status IN ('queued', 'running')
                ORDER BY created_at
            """).fetchall()
        result = []
        for row in rows:
            try:
                value = json.loads(dict(row)["snapshot_json"])
                if isinstance(value, dict):
                    result.append(value)
            except (TypeError, ValueError):
                continue
        return result

    def get(self, task_id: str) -> dict[str, Any] | None:
        with self.store._connection() as conn:
            row = self.store._execute(conn,
                "SELECT snapshot_json FROM atlas_autonomous_tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None
        try:
            value = json.loads(dict(row)["snapshot_json"])
            return value if isinstance(value, dict) else None
        except (TypeError, ValueError):
            return None
