from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator


DEFAULT_PROJECTS = (
    ("project-general", "General"),
    ("project-atlas", "Atlas"),
    ("project-shopify", "Shopify"),
    ("project-promo", "Промо"),
)


class AtlasStoreError(RuntimeError):
    pass


class TooManyJobs(AtlasStoreError):
    pass


class BudgetExceeded(AtlasStoreError):
    pass


class AtlasStore:
    """Small durable state layer shared by jobs, projects, memory and budgets."""

    def __init__(
        self,
        database_url: str | None = None,
        sqlite_path: str | None = None,
        max_active_jobs: int = 3,
    ) -> None:
        self.database_url = (
            database_url
            or os.environ.get("ATLAS_DATABASE_URL")
            or os.environ.get("DATABASE_URL")
            or ""
        ).strip()
        self.sqlite_path = sqlite_path or os.environ.get(
            "ATLAS_DB_PATH", "/tmp/atlas_state.db"
        )
        self.max_active_jobs = max(1, int(max_active_jobs))
        self.backend = "postgres" if self.database_url.startswith(("postgres://", "postgresql://")) else "sqlite-fallback"
        self._psycopg = None
        self._dict_row = None
        self.initialized = False

    def initialize(self) -> None:
        if self.backend == "postgres":
            try:
                import psycopg
                from psycopg.rows import dict_row
            except ImportError as exc:
                raise AtlasStoreError(
                    "DATABASE_URL is configured but psycopg is not installed"
                ) from exc
            self._psycopg = psycopg
            self._dict_row = dict_row
        else:
            path = Path(self.sqlite_path)
            path.parent.mkdir(parents=True, exist_ok=True)

        statements = [
            """
            CREATE TABLE IF NOT EXISTS atlas_projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL,
                last_response_id TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS atlas_memories (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                content TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL,
                UNIQUE(project_id, memory_key)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS atlas_jobs (
                job_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                code INTEGER,
                safe_retry INTEGER NOT NULL DEFAULT 0,
                retry_count INTEGER NOT NULL DEFAULT 0,
                cancel_requested INTEGER NOT NULL DEFAULT 0,
                worker_id TEXT,
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL,
                started_at DOUBLE PRECISION,
                completed_at DOUBLE PRECISION
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS atlas_files (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                media_type TEXT NOT NULL,
                data TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                content_hash TEXT NOT NULL,
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL,
                UNIQUE(project_id, content_hash)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS atlas_secrets (
                name TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS atlas_push_subscriptions (
                id TEXT PRIMARY KEY,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                user_agent TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                last_error TEXT,
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS atlas_usage (
                id TEXT PRIMARY KEY,
                day TEXT NOT NULL,
                job_id TEXT,
                project_id TEXT,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                web_calls INTEGER NOT NULL DEFAULT 0,
                claude_calls INTEGER NOT NULL DEFAULT 0,
                cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
                created_at DOUBLE PRECISION NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS atlas_budget_reservations (
                id TEXT PRIMARY KEY,
                day TEXT NOT NULL,
                job_id TEXT,
                model TEXT NOT NULL,
                amount_usd DOUBLE PRECISION NOT NULL,
                status TEXT NOT NULL,
                created_at DOUBLE PRECISION NOT NULL,
                updated_at DOUBLE PRECISION NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS atlas_actions (
                id TEXT PRIMARY KEY,
                job_id TEXT,
                project_id TEXT,
                tool TEXT NOT NULL,
                status TEXT NOT NULL,
                detail_json TEXT,
                duration_ms INTEGER,
                created_at DOUBLE PRECISION NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS atlas_jobs_status_idx ON atlas_jobs(status, created_at)",
            "CREATE INDEX IF NOT EXISTS atlas_jobs_project_idx ON atlas_jobs(project_id, created_at)",
            "CREATE INDEX IF NOT EXISTS atlas_memories_project_idx ON atlas_memories(project_id, updated_at)",
            "CREATE INDEX IF NOT EXISTS atlas_files_project_idx ON atlas_files(project_id, updated_at)",
            "CREATE INDEX IF NOT EXISTS atlas_push_enabled_idx ON atlas_push_subscriptions(enabled, updated_at)",
            "CREATE INDEX IF NOT EXISTS atlas_usage_day_idx ON atlas_usage(day, created_at)",
            "CREATE INDEX IF NOT EXISTS atlas_actions_project_idx ON atlas_actions(project_id, created_at)",
        ]

        with self._connection(immediate=True) as conn:
            for statement in statements:
                self._execute(conn, statement)
            now = time.time()
            for project_id, name in DEFAULT_PROJECTS:
                self._execute(
                    conn,
                    """
                    INSERT INTO atlas_projects(id, name, created_at, updated_at)
                    VALUES(?, ?, ?, ?)
                    ON CONFLICT(id) DO NOTHING
                    """,
                    (project_id, name, now, now),
                )
        self.initialized = True

    def close(self) -> None:
        self.initialized = False

    @contextmanager
    def _connection(self, immediate: bool = False) -> Iterator[Any]:
        if self.backend == "postgres":
            if self._psycopg is None:
                raise AtlasStoreError("Store is not initialized")
            conn = self._psycopg.connect(
                self.database_url,
                autocommit=False,
                row_factory=self._dict_row,
            )
        else:
            conn = sqlite3.connect(self.sqlite_path, timeout=30)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 30000")
            if immediate:
                conn.execute("BEGIN IMMEDIATE")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _sql(self, statement: str) -> str:
        return statement.replace("?", "%s") if self.backend == "postgres" else statement

    def _execute(self, conn: Any, statement: str, params: tuple[Any, ...] = ()) -> Any:
        cursor = conn.cursor()
        cursor.execute(self._sql(statement), params)
        return cursor

    @staticmethod
    def _dict(row: Any) -> dict[str, Any] | None:
        return dict(row) if row is not None else None

    @staticmethod
    def _loads(value: str | None, fallback: Any) -> Any:
        if not value:
            return fallback
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _project_id(value: str | None) -> str:
        value = (value or "project-general").strip()[:80]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            return "project-general"
        return value

    @staticmethod
    def _today() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _advisory_lock(self, conn: Any, key: int) -> None:
        if self.backend == "postgres":
            self._execute(conn, "SELECT pg_advisory_xact_lock(?)", (key,))

    def ensure_project(self, project_id: str | None) -> dict[str, Any]:
        project_id = self._project_id(project_id)
        now = time.time()
        with self._connection(immediate=True) as conn:
            self._execute(
                conn,
                """
                INSERT INTO atlas_projects(id, name, created_at, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(id) DO NOTHING
                """,
                (project_id, project_id.removeprefix("project-").replace("-", " ").title(), now, now),
            )
            row = self._execute(
                conn, "SELECT * FROM atlas_projects WHERE id = ?", (project_id,)
            ).fetchone()
        return self._dict(row) or {}

    def create_project(self, name: str) -> dict[str, Any]:
        clean_name = " ".join((name or "").split())[:80]
        if not clean_name:
            raise AtlasStoreError("Project name is required")
        project_id = f"project-{uuid.uuid4().hex[:16]}"
        now = time.time()
        with self._connection(immediate=True) as conn:
            self._execute(
                conn,
                "INSERT INTO atlas_projects(id, name, created_at, updated_at) VALUES(?, ?, ?, ?)",
                (project_id, clean_name, now, now),
            )
        return self.get_project(project_id) or {}

    def get_project(self, project_id: str | None) -> dict[str, Any] | None:
        project_id = self._project_id(project_id)
        with self._connection() as conn:
            row = self._execute(
                conn, "SELECT * FROM atlas_projects WHERE id = ?", (project_id,)
            ).fetchone()
        return self._dict(row)

    def list_projects(self) -> list[dict[str, Any]]:
        order = {project_id: index for index, (project_id, _) in enumerate(DEFAULT_PROJECTS)}
        with self._connection() as conn:
            rows = self._execute(
                conn, "SELECT * FROM atlas_projects ORDER BY created_at, name"
            ).fetchall()
        result = [dict(row) for row in rows]
        result.sort(key=lambda item: (order.get(item["id"], 100), item["created_at"], item["name"].lower()))
        return result

    def update_project_response(self, project_id: str | None, response_id: str | None) -> None:
        project_id = self._project_id(project_id)
        self.ensure_project(project_id)
        with self._connection(immediate=True) as conn:
            self._execute(
                conn,
                "UPDATE atlas_projects SET last_response_id = ?, updated_at = ? WHERE id = ?",
                (response_id, time.time(), project_id),
            )

    def remember(
        self,
        project_id: str | None,
        content: str,
        kind: str = "note",
    ) -> dict[str, Any]:
        project_id = self._project_id(project_id)
        self.ensure_project(project_id)
        clean_content = " ".join((content or "").split())[:12000]
        clean_kind = re.sub(r"[^a-z0-9_-]", "-", (kind or "note").lower())[:32] or "note"
        if not clean_content:
            raise AtlasStoreError("Memory content is required")
        memory_key = hashlib.sha256(
            f"{clean_kind}\0{clean_content}".encode("utf-8")
        ).hexdigest()
        memory_id = "memory-" + hashlib.sha256(
            f"{project_id}\0{memory_key}".encode("utf-8")
        ).hexdigest()[:24]
        now = time.time()
        with self._connection(immediate=True) as conn:
            self._execute(
                conn,
                """
                INSERT INTO atlas_memories(
                    id, project_id, kind, content, memory_key, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, memory_key) DO UPDATE SET
                    kind = excluded.kind,
                    content = excluded.content,
                    updated_at = excluded.updated_at
                """,
                (
                    memory_id,
                    project_id,
                    clean_kind,
                    clean_content,
                    memory_key,
                    now,
                    now,
                ),
            )
            row = self._execute(
                conn,
                "SELECT * FROM atlas_memories WHERE project_id = ? AND memory_key = ?",
                (project_id, memory_key),
            ).fetchone()
        return self._dict(row) or {}

    def search_memories(
        self,
        project_id: str | None,
        query: str = "",
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        project_id = self._project_id(project_id)
        limit = max(1, min(int(limit), 30))
        words = []
        for word in re.findall(r"[\w-]+", (query or "").lower(), flags=re.UNICODE):
            if len(word) >= 3 and word not in words:
                words.append(word)
            if len(words) == 6:
                break
        where = ["project_id = ?"]
        params: list[Any] = [project_id]
        if words:
            where.append("(" + " OR ".join("LOWER(content) LIKE ?" for _ in words) + ")")
            params.extend(f"%{word}%" for word in words)
        params.append(limit)
        with self._connection() as conn:
            rows = self._execute(
                conn,
                f"""
                SELECT id, project_id, kind, content, created_at, updated_at
                FROM atlas_memories
                WHERE {' AND '.join(where)}
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def memory_context(
        self,
        project_id: str | None,
        query: str,
        max_chars: int = 8000,
    ) -> str:
        memories = self.search_memories(project_id, query, limit=14)
        if not memories:
            memories = self.search_memories(project_id, "", limit=10)
        chunks = []
        size = 0
        for memory in memories:
            line = f"- [{memory['kind']}] {memory['content']}"
            if size + len(line) > max_chars:
                break
            chunks.append(line)
            size += len(line)
        return "\n".join(chunks)

    def delete_memory(self, project_id: str | None, memory_id: str) -> bool:
        project_id = self._project_id(project_id)
        memory_id = (memory_id or "").strip()[:100]
        if not memory_id:
            return False
        with self._connection(immediate=True) as conn:
            cursor = self._execute(
                conn,
                "DELETE FROM atlas_memories WHERE id = ? AND project_id = ?",
                (memory_id, project_id),
            )
        return cursor.rowcount == 1

    def get_or_create_secret(self, name: str, value: str) -> str:
        clean_name = re.sub(r"[^a-z0-9_.-]", "-", (name or "").lower())[:100]
        if not clean_name or not value:
            raise AtlasStoreError("Secret name and value are required")
        now = time.time()
        with self._connection(immediate=True) as conn:
            self._execute(
                conn,
                """
                INSERT INTO atlas_secrets(name, value, created_at, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(name) DO NOTHING
                """,
                (clean_name, value, now, now),
            )
            row = self._execute(
                conn, "SELECT value FROM atlas_secrets WHERE name = ?", (clean_name,)
            ).fetchone()
        return str(dict(row)["value"])

    def upsert_push_subscription(
        self,
        *,
        endpoint: str,
        p256dh: str,
        auth: str,
        user_agent: str = "",
    ) -> dict[str, Any]:
        endpoint = (endpoint or "").strip()[:4000]
        p256dh = (p256dh or "").strip()[:1000]
        auth = (auth or "").strip()[:1000]
        if not endpoint.startswith("https://") or not p256dh or not auth:
            raise AtlasStoreError("Invalid push subscription")
        subscription_id = "push-" + hashlib.sha256(endpoint.encode("utf-8")).hexdigest()[:24]
        now = time.time()
        with self._connection(immediate=True) as conn:
            self._execute(
                conn,
                """
                INSERT INTO atlas_push_subscriptions(
                    id, endpoint, p256dh, auth, user_agent, enabled,
                    last_error, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, 1, NULL, ?, ?)
                ON CONFLICT(endpoint) DO UPDATE SET
                    p256dh = excluded.p256dh,
                    auth = excluded.auth,
                    user_agent = excluded.user_agent,
                    enabled = 1,
                    last_error = NULL,
                    updated_at = excluded.updated_at
                """,
                (subscription_id, endpoint, p256dh, auth, (user_agent or "")[:500], now, now),
            )
            row = self._execute(
                conn,
                """
                SELECT id, enabled, created_at, updated_at
                FROM atlas_push_subscriptions WHERE endpoint = ?
                """,
                (endpoint,),
            ).fetchone()
        return self._dict(row) or {}

    def list_push_subscriptions(self) -> list[dict[str, Any]]:
        with self._connection() as conn:
            rows = self._execute(
                conn,
                """
                SELECT id, endpoint, p256dh, auth, user_agent, created_at, updated_at
                FROM atlas_push_subscriptions
                WHERE enabled = 1
                ORDER BY updated_at DESC
                """,
            ).fetchall()
        return [dict(row) for row in rows]

    def disable_push_subscription(self, subscription_id: str, error: str = "") -> bool:
        with self._connection(immediate=True) as conn:
            cursor = self._execute(
                conn,
                """
                UPDATE atlas_push_subscriptions
                SET enabled = 0, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                ((error or "")[:1000], time.time(), (subscription_id or "")[:100]),
            )
        return cursor.rowcount == 1

    def delete_push_subscription(self, endpoint: str) -> bool:
        endpoint = (endpoint or "").strip()[:4000]
        with self._connection(immediate=True) as conn:
            cursor = self._execute(
                conn, "DELETE FROM atlas_push_subscriptions WHERE endpoint = ?", (endpoint,)
            )
        return cursor.rowcount == 1

    def push_subscription_count(self) -> int:
        with self._connection() as conn:
            row = self._execute(
                conn,
                "SELECT COUNT(*) AS total FROM atlas_push_subscriptions WHERE enabled = 1",
            ).fetchone()
        return int(dict(row)["total"] or 0)

    @staticmethod
    def _attachment_size(data: str) -> int:
        payload = (data or "").split(",", 1)[-1]
        padding = len(payload) - len(payload.rstrip("="))
        return max(0, (len(payload) * 3) // 4 - padding)

    def save_file(
        self,
        project_id: str | None,
        *,
        name: str,
        media_type: str,
        data: str,
    ) -> dict[str, Any]:
        project_id = self._project_id(project_id)
        self.ensure_project(project_id)
        clean_name = re.sub(r"[\\x00-\\x1f\\x7f]+", " ", Path(name or "file").name).strip()[:180] or "file"
        clean_type = (media_type or "application/octet-stream").strip().lower()[:120]
        clean_data = data or ""
        if not clean_data:
            raise AtlasStoreError("File data is required")
        content_hash = hashlib.sha256(clean_data.encode("utf-8")).hexdigest()
        file_id = "file-" + hashlib.sha256(
            f"{project_id}\\0{content_hash}".encode("utf-8")
        ).hexdigest()[:24]
        size_bytes = self._attachment_size(clean_data)
        now = time.time()
        with self._connection(immediate=True) as conn:
            self._execute(
                conn,
                """
                INSERT INTO atlas_files(
                    id, project_id, name, media_type, data, size_bytes,
                    content_hash, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id, content_hash) DO UPDATE SET
                    name = excluded.name,
                    media_type = excluded.media_type,
                    updated_at = excluded.updated_at
                """,
                (file_id, project_id, clean_name, clean_type, clean_data, size_bytes, content_hash, now, now),
            )
            row = self._execute(
                conn,
                """
                SELECT id, project_id, name, media_type, size_bytes, created_at, updated_at
                FROM atlas_files WHERE id = ? AND project_id = ?
                """,
                (file_id, project_id),
            ).fetchone()
        return self._dict(row) or {}

    def save_attachments(
        self, project_id: str | None, attachments: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        saved = []
        for attachment in attachments[:4]:
            if not isinstance(attachment, dict):
                continue
            saved.append(
                self.save_file(
                    project_id,
                    name=str(attachment.get("name") or "file"),
                    media_type=str(attachment.get("media_type") or "application/octet-stream"),
                    data=str(attachment.get("data") or ""),
                )
            )
        return saved

    def list_files(
        self, project_id: str | None, limit: int = 100
    ) -> list[dict[str, Any]]:
        project_id = self._project_id(project_id)
        limit = max(1, min(int(limit), 200))
        with self._connection() as conn:
            rows = self._execute(
                conn,
                """
                SELECT id, project_id, name, media_type, size_bytes, created_at, updated_at
                FROM atlas_files
                WHERE project_id = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_file(
        self, project_id: str | None, file_id: str
    ) -> dict[str, Any] | None:
        project_id = self._project_id(project_id)
        file_id = (file_id or "").strip()[:100]
        with self._connection() as conn:
            row = self._execute(
                conn,
                """
                SELECT id, project_id, name, media_type, data, size_bytes, created_at, updated_at
                FROM atlas_files WHERE id = ? AND project_id = ?
                """,
                (file_id, project_id),
            ).fetchone()
        return self._dict(row)

    def delete_file(self, project_id: str | None, file_id: str) -> bool:
        project_id = self._project_id(project_id)
        file_id = (file_id or "").strip()[:100]
        if not file_id:
            return False
        with self._connection(immediate=True) as conn:
            cursor = self._execute(
                conn,
                "DELETE FROM atlas_files WHERE id = ? AND project_id = ?",
                (file_id, project_id),
            )
        return cursor.rowcount == 1

    def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_id = self._project_id(payload.get("project_id"))
        self.ensure_project(project_id)
        payload = dict(payload)
        payload["project_id"] = project_id
        safe_retry = int(
            not bool(payload.get("allow_writes"))
            and not bool(payload.get("attachments"))
        )
        job_id = uuid.uuid4().hex
        now = time.time()
        with self._connection(immediate=True) as conn:
            self._advisory_lock(conn, 19481001)
            active = self._execute(
                conn,
                "SELECT COUNT(*) AS total FROM atlas_jobs WHERE status IN ('queued', 'running')",
            ).fetchone()
            if int(dict(active)["total"]) >= self.max_active_jobs:
                raise TooManyJobs("Too many active jobs")
            self._execute(
                conn,
                """
                INSERT INTO atlas_jobs(
                    job_id, project_id, status, payload_json, safe_retry,
                    created_at, updated_at
                ) VALUES(?, ?, 'queued', ?, ?, ?, ?)
                """,
                (
                    job_id,
                    project_id,
                    json.dumps(payload, ensure_ascii=False),
                    safe_retry,
                    now,
                    now,
                ),
            )
        return self.get_job(job_id) or {}

    def claim_next_job(self, worker_id: str) -> dict[str, Any] | None:
        now = time.time()
        with self._connection(immediate=True) as conn:
            self._advisory_lock(conn, 19481002)
            suffix = " FOR UPDATE SKIP LOCKED" if self.backend == "postgres" else ""
            row = self._execute(
                conn,
                """
                SELECT * FROM atlas_jobs
                WHERE status = 'queued' AND cancel_requested = 0
                ORDER BY created_at
                LIMIT 1
                """ + suffix,
            ).fetchone()
            if row is None:
                return None
            job_id = dict(row)["job_id"]
            updated = self._execute(
                conn,
                """
                UPDATE atlas_jobs
                SET status = 'running', worker_id = ?, started_at = COALESCE(started_at, ?),
                    updated_at = ?
                WHERE job_id = ? AND status = 'queued' AND cancel_requested = 0
                """,
                (worker_id, now, now, job_id),
            )
            if updated.rowcount != 1:
                return None
            claimed = self._execute(
                conn, "SELECT * FROM atlas_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._format_job(self._dict(claimed))

    def touch_job(self, job_id: str, worker_id: str) -> bool:
        with self._connection(immediate=True) as conn:
            cursor = self._execute(
                conn,
                """
                UPDATE atlas_jobs SET updated_at = ?
                WHERE job_id = ? AND worker_id = ? AND status = 'running'
                    AND cancel_requested = 0
                """,
                (time.time(), job_id, worker_id),
            )
        return cursor.rowcount == 1

    def recover_stale_jobs(self, stale_after: float = 90.0) -> dict[str, int]:
        cutoff = time.time() - max(0.0, stale_after)
        recovered = 0
        failed = 0
        with self._connection(immediate=True) as conn:
            self._advisory_lock(conn, 19481003)
            rows = self._execute(
                conn,
                """
                SELECT job_id, safe_retry, retry_count, cancel_requested
                FROM atlas_jobs
                WHERE status = 'running' AND updated_at <= ?
                """,
                (cutoff,),
            ).fetchall()
            for raw in rows:
                row = dict(raw)
                self._execute(
                    conn,
                    """
                    UPDATE atlas_budget_reservations
                    SET status = 'released', updated_at = ?
                    WHERE job_id = ? AND status = 'active'
                    """,
                    (time.time(), row["job_id"]),
                )
                if row["cancel_requested"]:
                    now = time.time()
                    self._execute(
                        conn,
                        """
                        UPDATE atlas_jobs SET status = 'cancelled', error = ?,
                            completed_at = ?, updated_at = ?
                        WHERE job_id = ? AND status = 'running'
                        """,
                        ("Задача остановлена.", now, now, row["job_id"]),
                    )
                    continue
                if row["safe_retry"] and int(row["retry_count"]) < 1:
                    self._execute(
                        conn,
                        """
                        UPDATE atlas_jobs SET status = 'queued', retry_count = retry_count + 1,
                            worker_id = NULL, started_at = NULL, updated_at = ?
                        WHERE job_id = ? AND status = 'running'
                        """,
                        (time.time(), row["job_id"]),
                    )
                    recovered += 1
                else:
                    now = time.time()
                    self._execute(
                        conn,
                        """
                        UPDATE atlas_jobs SET status = 'error', error = ?, code = 503,
                            completed_at = ?, updated_at = ?
                        WHERE job_id = ? AND status = 'running'
                        """,
                        (
                            "Задача была прервана перезапуском Atlas. Небезопасный повтор не выполнялся.",
                            now,
                            now,
                            row["job_id"],
                        ),
                    )
                    failed += 1
        return {"recovered": recovered, "failed": failed}

    def is_cancel_requested(self, job_id: str) -> bool:
        with self._connection() as conn:
            row = self._execute(
                conn,
                "SELECT status, cancel_requested FROM atlas_jobs WHERE job_id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return True
        data = dict(row)
        return bool(data["cancel_requested"]) or data["status"] == "cancelled"

    def finish_job(
        self,
        job_id: str,
        answer: str,
        response_id: str | None,
        meta: dict[str, Any] | None = None,
    ) -> bool:
        now = time.time()
        result = {
            "answer": answer,
            "response_id": response_id,
            "meta": meta or {},
        }
        with self._connection(immediate=True) as conn:
            cursor = self._execute(
                conn,
                """
                UPDATE atlas_jobs
                SET status = 'done', result_json = ?, error = NULL, code = NULL,
                    completed_at = ?, updated_at = ?
                WHERE job_id = ? AND status = 'running' AND cancel_requested = 0
                """,
                (json.dumps(result, ensure_ascii=False), now, now, job_id),
            )
        return cursor.rowcount == 1

    def fail_job(self, job_id: str, error: str, code: int = 500) -> bool:
        now = time.time()
        with self._connection(immediate=True) as conn:
            cursor = self._execute(
                conn,
                """
                UPDATE atlas_jobs
                SET status = 'error', error = ?, code = ?, completed_at = ?, updated_at = ?
                WHERE job_id = ? AND status IN ('queued', 'running')
                    AND cancel_requested = 0
                """,
                ((error or "Atlas error")[:1000], int(code), now, now, job_id),
            )
        return cursor.rowcount == 1

    def cancel_job(self, job_id: str) -> dict[str, Any] | None:
        now = time.time()
        with self._connection(immediate=True) as conn:
            row = self._execute(
                conn, "SELECT status FROM atlas_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                return None
            if dict(row)["status"] in {"queued", "running"}:
                self._execute(
                    conn,
                    """
                    UPDATE atlas_jobs
                    SET status = 'cancelled', cancel_requested = 1, error = ?,
                        completed_at = ?, updated_at = ?
                    WHERE job_id = ?
                    """,
                    ("Задача остановлена.", now, now, job_id),
                )
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = self._execute(
                conn, "SELECT * FROM atlas_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._format_job(self._dict(row))

    def _format_job(self, row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        row["payload"] = self._loads(row.pop("payload_json", None), {})
        result = self._loads(row.pop("result_json", None), {})
        row["result"] = result
        row["answer"] = result.get("answer", "")
        row["response_id"] = result.get("response_id")
        row["meta"] = result.get("meta", {})
        row["cancel_requested"] = bool(row.get("cancel_requested"))
        row["safe_retry"] = bool(row.get("safe_retry"))
        return row

    def list_recent_jobs(
        self, project_id: str | None, limit: int = 30
    ) -> list[dict[str, Any]]:
        project_id = self._project_id(project_id)
        limit = max(1, min(int(limit), 100))
        with self._connection() as conn:
            rows = self._execute(
                conn,
                """
                SELECT * FROM atlas_jobs
                WHERE project_id = ? AND status IN ('done', 'error', 'cancelled')
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        result = [self._format_job(dict(row)) for row in rows]
        result.reverse()
        return [item for item in result if item]

    def prune_jobs(self, retention_seconds: float = 30 * 24 * 3600) -> int:
        cutoff = time.time() - max(3600.0, retention_seconds)
        with self._connection(immediate=True) as conn:
            cursor = self._execute(
                conn,
                """
                DELETE FROM atlas_jobs
                WHERE status IN ('done', 'error', 'cancelled') AND updated_at < ?
                """,
                (cutoff,),
            )
        return max(0, int(cursor.rowcount or 0))

    def reserve_budget(
        self,
        job_id: str | None,
        model: str,
        amount_usd: float,
        daily_limit_usd: float,
        task_limit_usd: float,
    ) -> dict[str, Any]:
        amount = max(0.0, float(amount_usd))
        if amount > float(task_limit_usd):
            raise BudgetExceeded(
                f"Estimated task cost USD {amount:.4f} exceeds task limit USD {task_limit_usd:.2f}"
            )
        day = self._today()
        reservation_id = uuid.uuid4().hex
        now = time.time()
        with self._connection(immediate=True) as conn:
            self._advisory_lock(conn, 19481004)
            if job_id:
                self._execute(
                    conn,
                    """
                    UPDATE atlas_budget_reservations SET status = 'released', updated_at = ?
                    WHERE job_id = ? AND status = 'active'
                    """,
                    (now, job_id),
                )
            spent_row = self._execute(
                conn,
                "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM atlas_usage WHERE day = ?",
                (day,),
            ).fetchone()
            reserved_row = self._execute(
                conn,
                """
                SELECT COALESCE(SUM(amount_usd), 0) AS total
                FROM atlas_budget_reservations
                WHERE day = ? AND status = 'active'
                """,
                (day,),
            ).fetchone()
            spent = float(dict(spent_row)["total"] or 0)
            reserved = float(dict(reserved_row)["total"] or 0)
            if spent + reserved + amount > float(daily_limit_usd):
                raise BudgetExceeded(
                    f"Daily Atlas budget USD {daily_limit_usd:.2f} would be exceeded"
                )
            self._execute(
                conn,
                """
                INSERT INTO atlas_budget_reservations(
                    id, day, job_id, model, amount_usd, status, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, 'active', ?, ?)
                """,
                (reservation_id, day, job_id, model, amount, now, now),
            )
        return {
            "id": reservation_id,
            "day": day,
            "amount_usd": amount,
            "model": model,
        }

    def complete_budget(
        self,
        reservation_id: str,
        *,
        job_id: str | None,
        project_id: str | None,
        model: str,
        input_tokens: int,
        output_tokens: int,
        web_calls: int,
        cost_usd: float,
    ) -> None:
        now = time.time()
        day = self._today()
        with self._connection(immediate=True) as conn:
            self._advisory_lock(conn, 19481004)
            self._execute(
                conn,
                """
                UPDATE atlas_budget_reservations
                SET status = 'completed', updated_at = ?
                WHERE id = ? AND status = 'active'
                """,
                (now, reservation_id),
            )
            self._execute(
                conn,
                """
                INSERT INTO atlas_usage(
                    id, day, job_id, project_id, model, input_tokens,
                    output_tokens, web_calls, claude_calls, cost_usd, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    day,
                    job_id,
                    self._project_id(project_id),
                    model,
                    max(0, int(input_tokens)),
                    max(0, int(output_tokens)),
                    max(0, int(web_calls)),
                    max(0.0, float(cost_usd)),
                    now,
                ),
            )

    def release_budget(self, reservation_id: str | None) -> None:
        if not reservation_id:
            return
        with self._connection(immediate=True) as conn:
            self._execute(
                conn,
                """
                UPDATE atlas_budget_reservations SET status = 'released', updated_at = ?
                WHERE id = ? AND status = 'active'
                """,
                (time.time(), reservation_id),
            )

    def budget_status(self, daily_limit_usd: float) -> dict[str, Any]:
        day = self._today()
        with self._connection() as conn:
            spent_row = self._execute(
                conn,
                "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM atlas_usage WHERE day = ?",
                (day,),
            ).fetchone()
            reserved_row = self._execute(
                conn,
                """
                SELECT COALESCE(SUM(amount_usd), 0) AS total
                FROM atlas_budget_reservations
                WHERE day = ? AND status = 'active'
                """,
                (day,),
            ).fetchone()
        spent = float(dict(spent_row)["total"] or 0)
        reserved = float(dict(reserved_row)["total"] or 0)
        return {
            "day": day,
            "spent_usd": round(spent, 6),
            "reserved_usd": round(reserved, 6),
            "daily_limit_usd": float(daily_limit_usd),
            "remaining_usd": round(max(0.0, float(daily_limit_usd) - spent - reserved), 6),
        }

    def claude_calls_today(self) -> int:
        with self._connection() as conn:
            row = self._execute(
                conn,
                "SELECT COALESCE(SUM(claude_calls), 0) AS total FROM atlas_usage WHERE day = ?",
                (self._today(),),
            ).fetchone()
        return int(dict(row)["total"] or 0)

    def record_claude_call(
        self, job_id: str | None, project_id: str | None, model: str
    ) -> None:
        with self._connection(immediate=True) as conn:
            self._execute(
                conn,
                """
                INSERT INTO atlas_usage(
                    id, day, job_id, project_id, model, input_tokens,
                    output_tokens, web_calls, claude_calls, cost_usd, created_at
                ) VALUES(?, ?, ?, ?, ?, 0, 0, 0, 1, 0, ?)
                """,
                (
                    uuid.uuid4().hex,
                    self._today(),
                    job_id,
                    self._project_id(project_id),
                    model,
                    time.time(),
                ),
            )

    def record_action(
        self,
        *,
        tool: str,
        status: str,
        job_id: str | None = None,
        project_id: str | None = None,
        detail: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        with self._connection(immediate=True) as conn:
            self._execute(
                conn,
                """
                INSERT INTO atlas_actions(
                    id, job_id, project_id, tool, status, detail_json,
                    duration_ms, created_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    job_id,
                    self._project_id(project_id),
                    (tool or "unknown")[:100],
                    (status or "unknown")[:40],
                    json.dumps(detail or {}, ensure_ascii=False)[:16000],
                    duration_ms,
                    time.time(),
                ),
            )

    def list_actions(
        self, project_id: str | None, limit: int = 50
    ) -> list[dict[str, Any]]:
        project_id = self._project_id(project_id)
        limit = max(1, min(int(limit), 200))
        with self._connection() as conn:
            rows = self._execute(
                conn,
                """
                SELECT * FROM atlas_actions
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["detail"] = self._loads(item.pop("detail_json", None), {})
            result.append(item)
        return result
