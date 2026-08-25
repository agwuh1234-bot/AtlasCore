from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable


TERMINAL = {"done", "failed", "blocked", "cancelled"}


@dataclass
class AutonomousStep:
    id: str
    title: str
    worker: str
    payload: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: str = "queued"
    attempts: int = 0
    max_attempts: int = 3
    result: Any = None
    error: str | None = None


@dataclass
class AutonomousTask:
    id: str
    goal: str
    steps: list[AutonomousStep]
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class AutonomousTaskEngine:
    """Dependency-aware, self-continuing multi-worker task engine.

    Workers are registered callables. Independent ready steps run concurrently.
    Failed safe steps retry up to max_attempts. A step can return
    {"status": "blocked", "reason": ...} when user approval/2FA is required;
    unrelated ready work continues.
    """

    def __init__(self, *, concurrency: int = 5) -> None:
        self.concurrency = max(1, concurrency)
        self.workers: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {}
        self.tasks: dict[str, AutonomousTask] = {}
        self._running: dict[str, asyncio.Task] = {}

    def register_worker(self, name: str, worker: Callable[[dict[str, Any]], Awaitable[Any]]) -> None:
        self.workers[name] = worker

    def submit(self, goal: str, steps: list[dict[str, Any]]) -> AutonomousTask:
        task_id = uuid.uuid4().hex
        parsed: list[AutonomousStep] = []
        seen: set[str] = set()
        for raw in steps:
            step_id = str(raw.get("id") or uuid.uuid4().hex[:12])
            if step_id in seen:
                raise ValueError(f"duplicate_step:{step_id}")
            seen.add(step_id)
            parsed.append(AutonomousStep(
                id=step_id,
                title=str(raw.get("title") or step_id),
                worker=str(raw["worker"]),
                payload=dict(raw.get("payload") or {}),
                depends_on=list(raw.get("depends_on") or []),
                max_attempts=max(1, min(int(raw.get("max_attempts", 3)), 10)),
            ))
        for step in parsed:
            missing = set(step.depends_on) - seen
            if missing:
                raise ValueError(f"missing_dependencies:{','.join(sorted(missing))}")
        task = AutonomousTask(task_id, goal, parsed)
        self.tasks[task_id] = task
        self._running[task_id] = asyncio.create_task(self._run(task), name=f"atlas-auto-{task_id[:8]}")
        return task

    async def _run(self, task: AutonomousTask) -> None:
        task.status = "running"
        sem = asyncio.Semaphore(self.concurrency)
        while True:
            done = {s.id for s in task.steps if s.status == "done"}
            active = [s for s in task.steps if s.status == "running"]
            ready = [s for s in task.steps if s.status == "queued" and set(s.depends_on) <= done]
            if ready:
                await asyncio.gather(*(self._execute_step(step, sem) for step in ready))
                task.updated_at = time.time()
                continue
            if active:
                await asyncio.sleep(.1)
                continue
            pending = [s for s in task.steps if s.status == "queued"]
            blocked = [s for s in task.steps if s.status == "blocked"]
            failed = [s for s in task.steps if s.status == "failed"]
            if pending:
                # Dependencies can no longer become successful.
                for step in pending:
                    step.status = "blocked"
                    step.error = "dependency_not_satisfied"
                blocked.extend(pending)
            task.status = "failed" if failed else "blocked" if blocked else "done"
            task.updated_at = time.time()
            return

    async def _execute_step(self, step: AutonomousStep, sem: asyncio.Semaphore) -> None:
        worker = self.workers.get(step.worker)
        if worker is None:
            step.status = "failed"
            step.error = f"unknown_worker:{step.worker}"
            return
        async with sem:
            while step.attempts < step.max_attempts:
                step.status = "running"
                step.attempts += 1
                try:
                    result = await worker(step.payload)
                    if isinstance(result, dict) and result.get("status") == "blocked":
                        step.status = "blocked"
                        step.error = str(result.get("reason") or "user_action_required")
                        step.result = result
                        return
                    step.result = result
                    step.status = "done"
                    step.error = None
                    return
                except asyncio.CancelledError:
                    step.status = "cancelled"
                    raise
                except Exception as exc:
                    step.error = f"{type(exc).__name__}: {exc}"[:1000]
                    if step.attempts >= step.max_attempts:
                        step.status = "failed"
                        return
                    step.status = "retrying"
                    await asyncio.sleep(min(2 ** (step.attempts - 1), 10))

    def snapshot(self, task_id: str) -> dict[str, Any] | None:
        task = self.tasks.get(task_id)
        if not task:
            return None
        return {
            "id": task.id,
            "goal": task.goal,
            "status": task.status,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "steps": [vars(s).copy() for s in task.steps],
        }
