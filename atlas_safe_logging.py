from __future__ import annotations

import json
import re
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

_SENSITIVE_CANONICAL_KEYS = {
    "".join(character for character in item.lower() if character.isalnum())
    for item in SENSITIVE_KEYS
}
_SENSITIVE_SUFFIXES = ("token", "secret", "password", "cookie", "credentials")
_AUTH_VALUE_RE = re.compile(r"(?i)\b(bearer|basic)\s+[^\s,;]+")
_QUERY_CREDENTIAL_RE = re.compile(
    r"(?i)([?&](?:access[_-]?token|refresh[_-]?token|api[_-]?key|apikey|token|secret|password|cookie)=)([^&#\s]+)"
)


def _canonical_key(key: Any) -> str:
    return "".join(character for character in str(key).strip().lower() if character.isalnum())


def _is_sensitive_key(key: Any) -> bool:
    canonical = _canonical_key(key)
    if canonical in _SENSITIVE_CANONICAL_KEYS:
        return True
    # Fail closed for common credential-field variants such as accessToken,
    # client-secret, webhook_token and session_cookie without broadly matching
    # unrelated keys that merely contain words like "key".
    return any(canonical.endswith(suffix) for suffix in _SENSITIVE_SUFFIXES)


def _sanitize_string(value: str) -> str:
    """Redact common auth credentials even when embedded in a free-form string."""
    redacted = _AUTH_VALUE_RE.sub(lambda match: f"{match.group(1)} <redacted>", value)
    redacted = _QUERY_CREDENTIAL_RE.sub(lambda match: f"{match.group(1)}<redacted>", redacted)
    if len(redacted) > 500:
        return redacted[:500] + "…<truncated>"
    return redacted


def sanitize_for_log(value: Any, *, max_depth: int = 5, max_items: int = 50) -> Any:
    """Return a bounded JSON-safe structure suitable for operational logs.

    Sensitive values are redacted by key. Deep/large structures are truncated to
    reduce accidental payload disclosure and log amplification.
    """
    if max_depth < 0:
        return "<truncated>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _sanitize_string(value)
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
