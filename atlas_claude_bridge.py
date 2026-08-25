from __future__ import annotations

import os
from typing import Any

import httpx


class ClaudeBridge:
    """Small Anthropic adapter for Atlas Executor.

    The bridge intentionally owns no user authentication. The FastAPI route that
    exposes it must enforce Atlas bridge/app authentication before calling it.
    """

    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = os.environ.get("CLAUDE_MODEL", "claude-opus-5")
        self.timeout_seconds = float(os.environ.get("CLAUDE_TIMEOUT_SECONDS", "120"))
        self.max_tokens = int(os.environ.get("CLAUDE_MAX_TOKENS", "2400"))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def ask(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        prompt = (prompt or "").strip()
        if not prompt:
            return {"ok": False, "error": "empty_prompt"}
        if not self.api_key:
            return {"ok": False, "error": "claude_not_configured"}

        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system or (
                "Ты Claude, независимый специалист внутри Atlas Executor. "
                "Проверяй решение критически, отмечай риски и конкретные исправления. "
                "Отвечай на языке запроса."
            ),
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                )
            if response.status_code >= 400:
                return {
                    "ok": False,
                    "error": "claude_http_error",
                    "status": response.status_code,
                    "details": response.text[:800],
                }
            data = response.json()
            text = "\n".join(
                block.get("text", "")
                for block in data.get("content", [])
                if block.get("type") == "text"
            ).strip()
            usage = data.get("usage") or {}
            return {
                "ok": True,
                "model": data.get("model") or self.model,
                "answer": text,
                "usage": {
                    "input_tokens": int(usage.get("input_tokens") or 0),
                    "output_tokens": int(usage.get("output_tokens") or 0),
                },
                "stop_reason": data.get("stop_reason"),
            }
        except Exception as exc:
            return {"ok": False, "error": "claude_request_failed", "details": str(exc)[:500]}
