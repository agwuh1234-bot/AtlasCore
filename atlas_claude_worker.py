from __future__ import annotations

import os
from typing import Any

from anthropic import AsyncAnthropic


class ClaudeWorker:
    """Isolated Claude reviewer/coding adviser.

    Claude never writes to the repository directly. Atlas owns acceptance,
    verification and application of proposed changes.
    """

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-opus-5")

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
        timeout = max(10.0, min(float(payload.get("timeout", 120)), 300.0))
        system = str(payload.get("system") or (
            "You are Atlas' senior code reviewer. Find concrete bugs, security risks, "
            "architecture problems and unnecessary custom code. Return actionable fixes. "
            "When useful, provide replacement code or a unified diff. Never claim files "
            "were changed: Atlas applies and verifies all changes."
        ))
        user_text = task if not context else f"TASK:\n{task}\n\nCONTEXT/CODE:\n{context}"

        client = AsyncAnthropic(api_key=self.api_key, timeout=timeout, max_retries=2)
        try:
            message = await client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_text}],
            )
        finally:
            await client.close()

        text = "\n".join(
            block.text for block in message.content
            if getattr(block, "type", None) == "text" and getattr(block, "text", None)
        ).strip()
        usage = getattr(message, "usage", None)
        return {
            "ok": True,
            "provider": "anthropic",
            "model": getattr(message, "model", self.model),
            "text": text,
            "usage": {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
            },
            "stop_reason": getattr(message, "stop_reason", None),
        }
