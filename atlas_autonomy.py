from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable, Protocol


TERMINAL = {"done", "failed", "blocked", "cancelled"}


class CheckpointStore(Protocol):
    def save(self, task: dict[str, Any]) -> None: ...
    def load_active(self) -> list[dict[str, Any]]: ...


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

    Independent ready steps run concurrently. Safe failures retry automatically.
    Optional checkpoint_store makes every state transition durable and allows
    unfinished graphs to resume after a process/Railway restart.
    """

    def __init__(self, *, concurrency: int = 5, checkpoint_store: CheckpointStore | None = None) -> None:
        self.concurrency = max(1, concurrency)
        self.checkpoint_store = checkpoint_store
        self.workers: dict[str, Callable[[dict[str, Any]], Awaitable[Any]]] = {}
        self.tasks: dict[str, AutonomousTask] = {}
        self._running: dict[str, asyncio.Task] = {}

    def register_worker(self, name: str, worker: Callable[[dict[str, Any]], Awaitable[Any]]) -> None:
        self.workers[name] = worker

    def _checkpoint(self, task: AutonomousTask) -> None:
        task.updated_at = time.time()
        if self.checkpoint_store:
            self.checkpoint_store.save(self.snapshot(task.id) or {})

    @staticmethod
    def _parse_steps(steps: list[dict[str, Any]]) -> list[AutonomousStep]:
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
                status=str(raw.get("status") or "queued"),
                attempts=max(0, int(raw.get("attempts", 0))),
                max_attempts=max(1, min(int(raw.get("max_attempts", 3)), 10)),
                result=raw.get("result"),
                error=raw.get("error"),
            ))
        for step in parsed:
            missing = set(step.depends_on) - seen
            if missing:
                raise ValueError(f"missing_dependencies:{','.join(sorted(missing))}")
        return parsed

    def submit(self, goal: str, steps: list[dict[str, Any]]) -> AutonomousTask:
        task = AutonomousTask(uuid.uuid4().hex, goal, self._parse_steps(steps))
        self.tasks[task.id] = task
        self._checkpoint(task)
        self._start(task)
        return task

    def _start(self, task: AutonomousTask) -> None:
        if task.id not in self._running or self._running[task.id].done():
            self._running[task.id] = asyncio.create_task(self._run(task), name=f"atlas-auto-{task.id[:8]}")

    def resume_all(self) -> int:
        if not self.checkpoint_store:
            return 0
        resumed = 0
        for raw in self.checkpoint_store.load_active():
            task_id = str(raw.get("id") or "")
            if not task_id or task_id in self.tasks:
                continue
            steps = self._parse_steps(list(raw.get("steps") or []))
            # A process died while these were running/retrying; execution is safe
            # to resume from the step boundary, never from inside a side effect.
            for step in steps:
                if step.status in {"running", "retrying"}:
                    step.status = "queued"
            task = AutonomousTask(
                id=task_id,
                goal=str(raw.get("goal") or ""),
                steps=steps,
                status="queued",
                created_at=float(raw.get("created_at") or time.time()),
                updated_at=time.time(),
            )
            self.tasks[task.id] = task
            self._checkpoint(task)
            self._start(task)
            resumed += 1
        return resumed

    async def _run(self, task: AutonomousTask) -> None:
        task.status = "running"
        self._checkpoint(task)
        sem = asyncio.Semaphore(self.concurrency)
        while True:
            done = {s.id for s in task.steps if s.status == "done"}
            ready = [s for s in task.steps if s.status == "queued" and set(s.depends_on) <= done]
            if ready:
                await asyncio.gather(*(self._execute_step(task, step, sem) for step in ready))
                continue
            active = [s for s in task.steps if s.status in {"running", "retrying"}]
            if active:
                await asyncio.sleep(.1)
                continue
            pending = [s for s in task.steps if s.status == "queued"]
            blocked = [s for s in task.steps if s.status == "blocked"]
            failed = [s for s in task.steps if s.status == "failed"]
            if pending:
                for step in pending:
                    step.status = "blocked"
                    step.error = "dependency_not_satisfied"
                blocked.extend(pending)
            task.status = "failed" if failed else "blocked" if blocked else "done"
            self._checkpoint(task)
            return

    async def _execute_step(self, task: AutonomousTask, step: AutonomousStep, sem: asyncio.Semaphore) -> None:
        worker = self.workers.get(step.worker)
        if worker is None:
            step.status = "failed"
            step.error = f"unknown_worker:{step.worker}"
            self._checkpoint(task)
            return
        async with sem:
            while step.attempts < step.max_attempts:
                step.status = "running"
                step.attempts += 1
                self._checkpoint(task)
                try:
                    result = await worker(step.payload)
                    if isinstance(result, dict) and result.get("status") == "blocked":
                        step.status = "blocked"
                        step.error = str(result.get("reason") or "user_action_required")
                        step.result = result
                        self._checkpoint(task)
                        return
                    step.result = result
                    step.status = "done"
                    step.error = None
                    self._checkpoint(task)
                    return
                except asyncio.CancelledError:
                    step.status = "queued"
                    self._checkpoint(task)
                    raise
                except Exception as exc:
                    step.error = f"{type(exc).__name__}: {exc}"[:1000]
                    if step.attempts >= step.max_attempts:
                        step.status = "failed"
                        self._checkpoint(task)
                        return
                    step.status = "retrying"
                    self._checkpoint(task)
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
            "steps": [asdict(s) for s in task.steps],
        }
