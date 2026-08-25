from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import socket
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


class BrowserExecutorError(RuntimeError):
    pass


@dataclass
class BrowserArtifact:
    kind: str
    path: str


@dataclass
class BrowserResult:
    job_id: str
    ok: bool
    url: str
    title: str
    text: str
    artifacts: list[BrowserArtifact]
    actions: list[dict[str, Any]]
    error: str | None = None

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data["artifacts"] = [asdict(x) for x in self.artifacts]
        return data


class BrowserExecutor:
    """Small, auditable Playwright executor for Atlas.

    V1 deliberately exposes a narrow action vocabulary instead of arbitrary Python/JS.
    That gives Atlas useful browser hands while keeping network and execution boundaries
    reviewable. Persistent authenticated sessions can be added later as encrypted state.
    """

    ALLOWED_ACTIONS = {"goto", "click", "fill", "press", "wait", "screenshot", "extract"}

    def __init__(self, artifact_dir: str | None = None) -> None:
        self.artifact_dir = Path(artifact_dir or os.environ.get("ATLAS_BROWSER_ARTIFACT_DIR", "/tmp/atlas-browser"))
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.timeout_ms = int(os.environ.get("ATLAS_BROWSER_TIMEOUT_MS", "30000"))
        self.max_actions = int(os.environ.get("ATLAS_BROWSER_MAX_ACTIONS", "40"))

    @staticmethod
    def _validate_public_url(url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise BrowserExecutorError("Only public http/https URLs are allowed")
        host = parsed.hostname.lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            raise BrowserExecutorError("Local/private targets are blocked")
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise BrowserExecutorError(f"Host resolution failed: {host}") from exc
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if not ip.is_global:
                raise BrowserExecutorError("Local/private targets are blocked")
        return url

    async def run(self, *, start_url: str, actions: list[dict[str, Any]]) -> BrowserResult:
        if len(actions) > self.max_actions:
            raise BrowserExecutorError(f"Too many browser actions; max={self.max_actions}")
        self._validate_public_url(start_url)
        for action in actions:
            if action.get("type") not in self.ALLOWED_ACTIONS:
                raise BrowserExecutorError(f"Unsupported browser action: {action.get('type')}")

        job_id = uuid.uuid4().hex
        job_dir = self.artifact_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        log: list[dict[str, Any]] = []
        artifacts: list[BrowserArtifact] = []

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserExecutorError("Playwright is not installed") from exc

        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                context = await browser.new_context(accept_downloads=False)
                page = await context.new_page()
                page.set_default_timeout(self.timeout_ms)
                await page.goto(start_url, wait_until="domcontentloaded")
                log.append({"type": "goto", "url": page.url, "at": time.time()})

                for index, action in enumerate(actions, 1):
                    kind = action["type"]
                    entry: dict[str, Any] = {"index": index, "type": kind, "at": time.time()}
                    if kind == "goto":
                        target = self._validate_public_url(str(action.get("url", "")))
                        await page.goto(target, wait_until="domcontentloaded")
                        entry["url"] = page.url
                    elif kind == "click":
                        selector = str(action.get("selector", ""))
                        await page.locator(selector).click()
                        entry["selector"] = selector
                    elif kind == "fill":
                        selector = str(action.get("selector", ""))
                        value = str(action.get("value", ""))
                        await page.locator(selector).fill(value)
                        entry.update(selector=selector, value_length=len(value))
                    elif kind == "press":
                        selector = str(action.get("selector", ""))
                        key = str(action.get("key", "Enter"))
                        await page.locator(selector).press(key)
                        entry.update(selector=selector, key=key)
                    elif kind == "wait":
                        ms = min(max(int(action.get("ms", 500)), 0), 10000)
                        await page.wait_for_timeout(ms)
                        entry["ms"] = ms
                    elif kind == "screenshot":
                        path = job_dir / f"step-{index}.png"
                        await page.screenshot(path=str(path), full_page=bool(action.get("full_page", True)))
                        artifacts.append(BrowserArtifact("screenshot", str(path)))
                        entry["artifact"] = str(path)
                    elif kind == "extract":
                        selector = str(action.get("selector", "body"))
                        text = await page.locator(selector).inner_text()
                        path = job_dir / f"extract-{index}.txt"
                        path.write_text(text[:200_000], encoding="utf-8")
                        artifacts.append(BrowserArtifact("text", str(path)))
                        entry.update(selector=selector, chars=min(len(text), 200_000))
                    log.append(entry)

                final_shot = job_dir / "final.png"
                await page.screenshot(path=str(final_shot), full_page=True)
                artifacts.append(BrowserArtifact("screenshot", str(final_shot)))
                body = (await page.locator("body").inner_text())[:50_000]
                result = BrowserResult(job_id, True, page.url, await page.title(), body, artifacts, log)
                (job_dir / "actions.json").write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
                await context.close()
                await browser.close()
                return result
        except Exception as exc:
            return BrowserResult(job_id, False, "", "", "", artifacts, log, f"{type(exc).__name__}: {exc}"[:1000])
