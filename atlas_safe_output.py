from __future__ import annotations

from typing import Any


def truncate_text(value: Any, *, max_chars: int) -> tuple[str, bool]:
    """Return bounded text and whether truncation happened.

    Tool responses can contain repository files, HTML, logs or model output. Keeping
    the bound in one helper prevents accidental prompt/context blowups.
    """
    text = "" if value is None else str(value)
    limit = max(1, int(max_chars))
    if len(text) <= limit:
        return text, False
    omitted = len(text) - limit
    return f"{text[:limit]}\n\n[truncated: {omitted} chars omitted]", True


def bounded_tool_result(value: Any, *, max_chars: int) -> dict[str, Any]:
    text, truncated = truncate_text(value, max_chars=max_chars)
    return {
        "content": text,
        "truncated": truncated,
        "content_chars": len("" if value is None else str(value)),
    }
