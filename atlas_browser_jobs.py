from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from atlas_browser_executor import BrowserExecutor


@dataclass
class BrowserJob:
    id: str
    start_url: str
    actions: list[dict[str, Any]]
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        # Never echo form values/secrets back from the submitted action list.
        data["actions"] = [
            {k: v for k, v in action.items() if k not in {"value", "password", "token", "secret"}}
            for action in self.actions
        ]
        return data


class BrowserJobManager:
    """In-process async queue for long browser work.

    V1 intentionally keeps a single worker to avoid concurrent use of the same
    authenticated browser identity. Durable DB-backed jobs can replace the
    storage layer without changing the public API.
    """

    def __init__(self, executor: BrowserExecutor | None = None, max_jobs: int = 100) -> None:
        self.executor = executor or BrowserExecutor()
        self.max_jobs = max_jobs
        self.jobs: dict[str, BrowserJob] = {}
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.worker_task: asyncio.Task | None = None

    def start(self) -> None:
        if self.worker_task is None or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._worker(), name="atlas-browser-worker")

    async def stop(self) -> None:
        if self.worker_task and not self.worker_task.done():
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

    async def submit(self, start_url: str, actions: list[dict[str, Any]]) -> BrowserJob:
        if len(self.jobs) >= self.max_jobs:
            terminal = [j for j in self.jobs.values() if j.status in {"done", "failed", "cancelled"}]
            terminal.sort(key=lambda j: j.finished_at or j.created_at)
            if terminal:
                self.jobs.pop(terminal[0].id, None)
            else:
                raise RuntimeError("browser_job_capacity_reached")
        # Validate before accepting the job.
        self.executor._validate_public_url(start_url)
        if len(actions) > self.executor.max_actions:
            raise ValueError("too_many_actions")
        for action in actions:
            if action.get("type") not in self.executor.ALLOWED_ACTIONS:
                raise ValueError(f"unsupported_action:{action.get('type')}")
        job = BrowserJob(uuid.uuid4().hex, start_url, actions)
        self.jobs[job.id] = job
        self.start()
        await self.queue.put(job.id)
        return job

    def get(self, job_id: str) -> BrowserJob | None:
        return self.jobs.get(job_id)

    def list(self, limit: int = 20) -> list[BrowserJob]:
        return sorted(self.jobs.values(), key=lambda j: j.created_at, reverse=True)[: max(1, min(limit, 100))]

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job or job.status != "queued":
            return False
        job.status = "cancelled"
        job.finished_at = time.time()
        return True

    async def _worker(self) -> None:
        while True:
            job_id = await self.queue.get()
            try:
                job = self.jobs.get(job_id)
                if not job or job.status == "cancelled":
                    continue
                job.status = "running"
                job.started_at = time.time()
                result = await self.executor.run(start_url=job.start_url, actions=job.actions)
                job.result = result.public()
                job.status = "done" if result.ok else "failed"
                job.error = result.error
                job.finished_at = time.time()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                job = self.jobs.get(job_id)
                if job:
                    job.status = "failed"
                    job.error = f"{type(exc).__name__}: {exc}"[:1000]
                    job.finished_at = time.time()
            finally:
                self.queue.task_done()
