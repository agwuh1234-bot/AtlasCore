from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger("atlas")


@dataclass(frozen=True)
class RuntimeConfig:
    github_repo: str
    github_branch: str
    claude_model: str
    max_file_lines: int
    max_file_content_chars: int
    allowed_user_ids: frozenset[int]

    @property
    def telegram_private(self) -> bool:
        return bool(self.allowed_user_ids)


def _bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid integer for {name}") from exc
    return max(minimum, min(value, maximum))


def _allowed_user_ids() -> frozenset[int]:
    values: set[int] = set()
    for item in os.environ.get("ALLOWED_USER_IDS", "").split(","):
        item = item.strip()
        if not item:
            continue
        try:
            values.add(int(item))
        except ValueError as exc:
            raise RuntimeError("ALLOWED_USER_IDS must contain numeric Telegram user IDs") from exc
    return frozenset(values)


def load_runtime_config() -> RuntimeConfig:
    config = RuntimeConfig(
        github_repo=os.environ.get("GITHUB_REPO", "agwuh1234-bot/AtlasCore").strip(),
        github_branch=os.environ.get("GITHUB_BRANCH", "main").strip() or "main",
        claude_model=os.environ.get("CLAUDE_MODEL", "claude-opus-5").strip(),
        max_file_lines=_bounded_int("ATLAS_MAX_FILE_LINES", 250, 20, 1000),
        max_file_content_chars=_bounded_int("ATLAS_MAX_FILE_CONTENT_CHARS", 12000, 1000, 100000),
        allowed_user_ids=_allowed_user_ids(),
    )
    if not config.github_repo or "/" not in config.github_repo:
        raise RuntimeError("GITHUB_REPO must use owner/repository format")
    if not config.allowed_user_ids:
        logger.warning(
            "ALLOWED_USER_IDS is empty; Telegram access is not restricted by user ID"
        )
    return config
