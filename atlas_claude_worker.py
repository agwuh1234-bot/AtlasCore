from __future__ import annotations

import os
from typing import Any

import httpx


class ClaudeWorker:
    """Small, isolated Claude worker for review/reasoning tasks.

    It intentionally has no repository write capability. Atlas/Verifier owns
    acceptance and application of any suggested patch.
    """

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
        self.base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def __call__(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            return {"status": "blocked", "reason": "anthropic_api_key_required"}

        task = str(payload.get("task") or payload.get("prompt") or "").strip()
        if not task:
            raise ValueError("claude_task_required")

        context = str(payload.get("context") or "")
        max_tokens = max(256, min(int(payload.get("max_tokens", 3000)), 8000))
        system = str(payload.get("system") or (
            "You are Atlas' senior code reviewer. Find concrete bugs, security risks, "
            "architecture problems and unnecessary custom code. Return actionable fixes. "
            "Do not claim you changed files; you only review and propose changes."
        ))
        user_text = task if not context else f"TASK:\n{task}\n\nCONTEXT/CODE:\n{context}"

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user_text}],
        }
        timeout = max(10.0, min(float(payload.get("timeout", 120)), 300.0))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(f"{self.base_url}/v1/messages", headers=headers, json=body)
            response.raise_for_status()
            data = response.json()

        text_parts = [
            block.get("text", "")
            for block in data.get("content", [])
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return {
            "ok": True,
            "provider": "anthropic",
            "model": data.get("model", self.model),
            "text": "\n".join(part for part in text_parts if part).strip(),
            "usage": data.get("usage") or {},
            "stop_reason": data.get("stop_reason"),
        }
