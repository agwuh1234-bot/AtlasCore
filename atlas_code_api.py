"""Read-only GitHub API surface for Atlas Code Studio.

Writes intentionally stay out of this router. Code changes continue to flow through
Atlas jobs + Developer Mode so the existing write policy and confirmations remain
in charge.
"""

from __future__ import annotations

import base64
import os
from typing import Callable

import httpx
from fastapi import APIRouter, Header, HTTPException, Request


DEFAULT_REPO = "agwuh1234-bot/AtlasCore"
DEFAULT_BRANCH = "main"
MAX_TEXT_BYTES = 450_000


def _safe_path(value: str | None) -> str:
    path = str(value or "").strip().replace("\\", "/").strip("/")
    if not path:
        return ""
    parts = [part for part in path.split("/") if part]
    if any(part in {".", ".."} for part in parts):
        raise HTTPException(status_code=400, detail="Invalid repository path")
    return "/".join(parts)


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def build_code_router(
    *,
    verify_request: Callable,
    repo: str = DEFAULT_REPO,
    branch: str = DEFAULT_BRANCH,
    token: str | None = None,
) -> APIRouter:
    router = APIRouter()
    github_token = token or os.environ.get("GITHUB_TOKEN", "")

    async def _get(path: str, *, params: dict | None = None) -> httpx.Response:
        if not github_token:
            raise HTTPException(status_code=503, detail="GitHub integration is not configured")
        url = f"https://api.github.com/repos/{repo}/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(url, headers=_headers(github_token), params=params)
        return response

    def _verify(request: Request, key: str | None) -> None:
        verify_request(request, key)

    @router.get("/app-code/tree")
    async def code_tree(
        request: Request,
        path: str = "",
        x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
    ):
        _verify(request, x_atlas_key)
        clean = _safe_path(path)
        endpoint = "contents" + (f"/{clean}" if clean else "")
        response = await _get(endpoint, params={"ref": branch})
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Repository path not found")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="GitHub tree request failed")
        payload = response.json()
        rows = payload if isinstance(payload, list) else [payload]
        items = []
        for item in rows[:250]:
            kind = str(item.get("type") or "")
            if kind not in {"file", "dir"}:
                continue
            items.append(
                {
                    "name": item.get("name"),
                    "path": item.get("path"),
                    "type": kind,
                    "size": int(item.get("size") or 0),
                    "sha": item.get("sha"),
                }
            )
        items.sort(key=lambda item: (item["type"] != "dir", str(item["name"]).lower()))
        parent = clean.rsplit("/", 1)[0] if "/" in clean else ""
        return {"ok": True, "repo": repo, "branch": branch, "path": clean, "parent": parent, "items": items}

    @router.get("/app-code/file")
    async def code_file(
        request: Request,
        path: str,
        x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
    ):
        _verify(request, x_atlas_key)
        clean = _safe_path(path)
        if not clean:
            raise HTTPException(status_code=400, detail="File path is required")
        response = await _get(f"contents/{clean}", params={"ref": branch})
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="File not found")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="GitHub file request failed")
        data = response.json()
        if data.get("type") != "file":
            raise HTTPException(status_code=400, detail="Path is not a file")
        size = int(data.get("size") or 0)
        if size > MAX_TEXT_BYTES:
            raise HTTPException(status_code=413, detail="File is too large for Code Studio preview")
        try:
            content = base64.b64decode(data.get("content") or "").decode("utf-8")
        except Exception as exc:
            raise HTTPException(status_code=415, detail="File is not UTF-8 text") from exc
        return {
            "ok": True,
            "repo": repo,
            "branch": branch,
            "path": clean,
            "sha": data.get("sha"),
            "size": size,
            "lines": len(content.splitlines()),
            "content": content,
            "html_url": data.get("html_url"),
        }

    @router.get("/app-code/recent-diff")
    async def recent_diff(
        request: Request,
        path: str,
        x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
    ):
        _verify(request, x_atlas_key)
        clean = _safe_path(path)
        if not clean:
            raise HTTPException(status_code=400, detail="File path is required")
        commits = await _get("commits", params={"path": clean, "sha": branch, "per_page": 1})
        if commits.status_code != 200:
            raise HTTPException(status_code=502, detail="GitHub history request failed")
        rows = commits.json()
        if not rows:
            return {"ok": True, "path": clean, "diff": None}
        sha = rows[0].get("sha")
        detail = await _get(f"commits/{sha}")
        if detail.status_code != 200:
            raise HTTPException(status_code=502, detail="GitHub commit request failed")
        data = detail.json()
        file_row = next((item for item in data.get("files", []) if item.get("filename") == clean), None)
        commit = data.get("commit") or {}
        author = commit.get("author") or {}
        return {
            "ok": True,
            "path": clean,
            "diff": {
                "sha": sha,
                "short_sha": str(sha or "")[:7],
                "message": (commit.get("message") or "").splitlines()[0],
                "date": author.get("date"),
                "status": (file_row or {}).get("status"),
                "additions": int((file_row or {}).get("additions") or 0),
                "deletions": int((file_row or {}).get("deletions") or 0),
                "patch": (file_row or {}).get("patch") or "",
            },
        }

    @router.get("/app-code/status")
    async def code_status(
        request: Request,
        x_atlas_key: str | None = Header(default=None, alias="X-Atlas-Key"),
    ):
        _verify(request, x_atlas_key)
        commit_response = await _get(f"commits/{branch}")
        if commit_response.status_code != 200:
            raise HTTPException(status_code=502, detail="GitHub branch request failed")
        commit_data = commit_response.json()
        sha = commit_data.get("sha")
        commit = commit_data.get("commit") or {}
        status_state = "unknown"
        statuses = []
        if sha:
            status_response = await _get(f"commits/{sha}/status")
            if status_response.status_code == 200:
                status_data = status_response.json()
                status_state = status_data.get("state") or "unknown"
                statuses = [
                    {
                        "context": item.get("context"),
                        "state": item.get("state"),
                        "description": item.get("description"),
                    }
                    for item in (status_data.get("statuses") or [])[:12]
                ]
        workflow = None
        runs = await _get("actions/runs", params={"branch": branch, "per_page": 1})
        if runs.status_code == 200:
            run_rows = runs.json().get("workflow_runs") or []
            if run_rows:
                row = run_rows[0]
                workflow = {
                    "name": row.get("name"),
                    "status": row.get("status"),
                    "conclusion": row.get("conclusion"),
                    "updated_at": row.get("updated_at"),
                    "html_url": row.get("html_url"),
                }
        return {
            "ok": True,
            "repo": repo,
            "branch": branch,
            "sha": sha,
            "short_sha": str(sha or "")[:7],
            "message": (commit.get("message") or "").splitlines()[0],
            "commit_date": ((commit.get("author") or {}).get("date")),
            "status": status_state,
            "statuses": statuses,
            "workflow": workflow,
        }

    return router
