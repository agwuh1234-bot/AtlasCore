from __future__ import annotations

import os
from typing import Any

import httpx


class ClaudeWorker:
    """Small Anthropic Messages API adapter for review/reasoning tasks.

    The worker is deliberately read-only: it returns Claude's proposal to Atlas.
    Atlas/Verifier decides whether any repository mutation is accepted.
    """

    API_URL = "https://api.anthropic.com/v1/messages"
    API_VERSION = "2023-06-01"

    def __init__(self, *, api_key: str | None = None, model: str | None = None, timeout: float = 120.0) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        self.timeout = max(5.0, min(float(timeout), 300.0))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            return {"status": "blocked", "reason": "anthropic_api_key_required"}

        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("claude_prompt_required")

        system = str(payload.get("system") or (
            "You are Atlas' senior code reviewer. Review the supplied code or plan. "
            "Find correctness, security, reliability and architecture issues. "
            "Return concrete proposed changes. Do not claim changes were applied."
        ))
        max_tokens = max(256, min(int(payload.get("max_tokens", 3000)), 8000))

        request = {
            "model": str(payload.get("model") or self.model),
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self.API_URL, headers=headers, json=request)
            response.raise_for_status()
            data = response.json()

        text = "\n".join(
            str(block.get("text") or "")
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ).strip()
        if not text:
            raise RuntimeError("claude_empty_response")
        usage = data.get("usage") or {}
        return {
            "ok": True,
            "provider": "anthropic",
            "model": data.get("model") or request["model"],
            "text": text,
            "usage": {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            },
            "stop_reason": data.get("stop_reason"),
        }


def register_claude_worker(engine: Any) -> ClaudeWorker:
    worker = ClaudeWorker()
    engine.register_worker("claude", worker)
    return worker
