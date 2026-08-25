from __future__ import annotations

import asyncio
from typing import Any

from atlas_browser_jobs import BrowserJobManager


class AutonomyWorkers:
    """Adapters that expose real Atlas capabilities to AutonomousTaskEngine."""

    def __init__(self, *, browser: BrowserJobManager | None = None) -> None:
        self.browser = browser

    async def browser_worker(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.browser is None:
            raise RuntimeError("browser_worker_not_configured")
        job = await self.browser.submit(
            str(payload["start_url"]),
            list(payload.get("actions") or []),
            session_name=payload.get("session_name"),
            save_session=bool(payload.get("save_session")),
        )
        timeout = max(5.0, min(float(payload.get("timeout", 120)), 300.0))
        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            current = self.browser.get(job.id)
            if current is None:
                raise RuntimeError("browser_job_disappeared")
            if current.status == "done":
                return current.result or {"ok": True}
            if current.status in {"failed", "cancelled"}:
                raise RuntimeError(current.error or f"browser_job_{current.status}")
            if asyncio.get_running_loop().time() >= deadline:
                self.browser.cancel(job.id)
                raise TimeoutError("browser_job_timeout")
            await asyncio.sleep(.25)

    async def verify_worker(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Deterministic assertions over prior/artifact data supplied by planner."""
        value = payload.get("value")
        checks = list(payload.get("checks") or [])
        failures: list[str] = []
        for check in checks:
            kind = check.get("type")
            expected = check.get("expected")
            if kind == "equals" and value != expected:
                failures.append(f"expected {expected!r}, got {value!r}")
            elif kind == "contains" and str(expected) not in str(value):
                failures.append(f"missing {expected!r}")
            elif kind == "truthy" and not value:
                failures.append("value is not truthy")
        if failures:
            raise AssertionError("; ".join(failures))
        return {"verified": True, "checks": len(checks)}

    async def approval_worker(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "blocked",
            "reason": str(payload.get("reason") or "user_approval_required"),
            "summary": str(payload.get("summary") or "Approval required"),
        }

    def register(self, engine: Any) -> None:
        engine.register_worker("browser", self.browser_worker)
        engine.register_worker("verify", self.verify_worker)
        engine.register_worker("approval", self.approval_worker)
