from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from atlas_autonomy import AutonomousTaskEngine
from atlas_autonomy_store import AtlasAutonomyStore
from atlas_autonomy_workers import AutonomyWorkers
from atlas_browser_executor import BrowserExecutor
from atlas_browser_jobs import BrowserJobManager
from atlas_browser_sessions import BrowserSessionStore
from atlas_store import AtlasStore


@dataclass
class AutonomyRuntime:
    engine: AutonomousTaskEngine
    browser_jobs: BrowserJobManager
    resumed_tasks: int = 0
    started: bool = False

    async def start(self) -> int:
        if self.started:
            return self.resumed_tasks
        self.browser_jobs.start()
        self.resumed_tasks = self.engine.resume_all()
        self.started = True
        return self.resumed_tasks

    async def stop(self) -> None:
        if not self.started:
            return
        for task in list(self.engine._running.values()):
            if not task.done():
                task.cancel()
        if self.engine._running:
            await asyncio.gather(*self.engine._running.values(), return_exceptions=True)
        await self.browser_jobs.stop()
        self.started = False

    def health(self) -> dict[str, Any]:
        snapshots = [self.engine.snapshot(task_id) for task_id in self.engine.tasks]
        active = sum(1 for item in snapshots if item and item.get("status") in {"queued", "running"})
        blocked = sum(1 for item in snapshots if item and item.get("status") == "blocked")
        return {
            "enabled": True,
            "started": self.started,
            "concurrency": self.engine.concurrency,
            "resumed_tasks": self.resumed_tasks,
            "tracked_tasks": len(self.engine.tasks),
            "active_tasks": active,
            "blocked_tasks": blocked,
            "workers": sorted(self.engine.workers),
            "encrypted_sessions": self.browser_jobs.executor.session_store is not None,
        }


def build_autonomy_runtime(store: AtlasStore) -> AutonomyRuntime:
    """Build the autonomous runtime without starting event-loop-owned tasks."""
    session_store = None
    if os.environ.get("ATLAS_BROWSER_SESSION_KEY"):
        session_store = BrowserSessionStore()

    executor = BrowserExecutor(session_store=session_store)
    browser_jobs = BrowserJobManager(executor=executor)
    checkpoints = AtlasAutonomyStore(store)
    try:
        requested = int(os.environ.get("ATLAS_AUTONOMY_CONCURRENCY", "5"))
    except ValueError:
        requested = 5
    engine = AutonomousTaskEngine(
        concurrency=max(1, min(requested, 10)),
        checkpoint_store=checkpoints,
    )
    AutonomyWorkers(browser=browser_jobs).register(engine)
    return AutonomyRuntime(engine=engine, browser_jobs=browser_jobs)


async def start_autonomy_runtime(runtime: AutonomyRuntime) -> int:
    """Compatibility helper; must be called from the owning asyncio loop."""
    return await runtime.start()
