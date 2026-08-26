from __future__ import annotations

import json
from typing import Any


SENSITIVE_KEYS = {
    "authorization",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "password",
    "secret",
    "cookie",
    "set-cookie",
    "headers",
    "body",
    "filecontent",
    "messages",
    "credentials",
}


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return normalized in {item.replace("-", "_") for item in SENSITIVE_KEYS}


def sanitize_for_log(value: Any, *, max_depth: int = 5, max_items: int = 50) -> Any:
    """Return a bounded JSON-safe structure suitable for operational logs.

    Sensitive values are redacted by key. Deep/large structures are truncated to
    reduce accidental payload disclosure and log amplification.
    """
    if max_depth < 0:
        return "<truncated>"
    if value is None or isinstance(value, (bool, int, float, str)):
        text = value
        if isinstance(text, str) and len(text) > 500:
            return text[:500] + "…<truncated>"
        return text
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, child) in enumerate(value.items()):
            if index >= max_items:
                result["<truncated_items>"] = len(value) - max_items
                break
            key_text = str(key)
            result[key_text] = "<redacted>" if _is_sensitive_key(key_text) else sanitize_for_log(
                child,
                max_depth=max_depth - 1,
                max_items=max_items,
            )
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        result = [sanitize_for_log(item, max_depth=max_depth - 1, max_items=max_items) for item in items[:max_items]]
        if len(items) > max_items:
            result.append(f"<truncated_items:{len(items) - max_items}>")
        return result
    return f"<{type(value).__name__}>"


def compact_json_for_log(value: Any, *, max_chars: int = 4000) -> str:
    safe = sanitize_for_log(value)
    rendered = json.dumps(safe, ensure_ascii=False, sort_keys=True, default=str)
    if len(rendered) > max_chars:
        return rendered[:max_chars] + "…<truncated>"
    return rendered
