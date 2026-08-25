from __future__ import annotations

import os
from dataclasses import dataclass

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

    async def stop(self) -> None:
        await self.browser_jobs.stop()


def build_autonomy_runtime(store: AtlasStore) -> AutonomyRuntime:
    """Build Atlas autonomous runtime from production configuration.

    Browser sessions are enabled only when the encryption key exists. This keeps
    local/test imports usable while production gets encrypted persisted auth state.
    """
    session_store = None
    if os.environ.get("ATLAS_BROWSER_SESSION_KEY"):
        session_store = BrowserSessionStore()

    executor = BrowserExecutor(session_store=session_store)
    browser_jobs = BrowserJobManager(executor=executor)
    checkpoints = AtlasAutonomyStore(store)
    engine = AutonomousTaskEngine(
        concurrency=max(1, min(int(os.environ.get("ATLAS_AUTONOMY_CONCURRENCY", "5")), 10)),
        checkpoint_store=checkpoints,
    )
    AutonomyWorkers(browser=browser_jobs).register(engine)
    return AutonomyRuntime(engine=engine, browser_jobs=browser_jobs)


def start_autonomy_runtime(runtime: AutonomyRuntime) -> int:
    runtime.browser_jobs.start()
    runtime.resumed_tasks = runtime.engine.resume_all()
    return runtime.resumed_tasks
