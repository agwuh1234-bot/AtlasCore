from __future__ import annotations

import secrets
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from atlas_browser_jobs import BrowserJobManager


class BrowserJobRequest(BaseModel):
    start_url: str = Field(min_length=8, max_length=2048)
    actions: list[dict[str, Any]] = Field(default_factory=list, max_length=40)


def build_browser_router(*, bridge_key: str, manager: BrowserJobManager | None = None) -> APIRouter:
    router = APIRouter(prefix="/executor/browser", tags=["browser-executor"])
    jobs = manager or BrowserJobManager()

    def authorize(provided: str | None) -> None:
        if not provided or not secrets.compare_digest(provided, bridge_key):
            raise HTTPException(status_code=401, detail="Unauthorized")

    @router.get("/capabilities")
    async def capabilities(x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key")):
        authorize(x_atlas_bridge_key)
        return {
            "ok": True,
            "mode": "background_jobs",
            "actions": sorted(jobs.executor.ALLOWED_ACTIONS),
            "max_actions": jobs.executor.max_actions,
        }

    @router.post("/jobs", status_code=202)
    async def submit(body: BrowserJobRequest, x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key")):
        authorize(x_atlas_bridge_key)
        try:
            job = await jobs.submit(body.start_url, body.actions)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"browser_job_rejected:{exc}") from exc
        return job.public()

    @router.get("/jobs/{job_id}")
    async def get_job(job_id: str, x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key")):
        authorize(x_atlas_bridge_key)
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job.public()

    @router.get("/jobs")
    async def list_jobs(limit: int = 20, x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key")):
        authorize(x_atlas_bridge_key)
        return {"jobs": [job.public() for job in jobs.list(limit)]}

    @router.delete("/jobs/{job_id}")
    async def cancel_job(job_id: str, x_atlas_bridge_key: str | None = Header(default=None, alias="X-Atlas-Bridge-Key")):
        authorize(x_atlas_bridge_key)
        if not jobs.get(job_id):
            raise HTTPException(status_code=404, detail="Job not found")
        if not jobs.cancel(job_id):
            raise HTTPException(status_code=409, detail="Only queued jobs can be cancelled")
        return {"ok": True, "job_id": job_id, "status": "cancelled"}

    return router
