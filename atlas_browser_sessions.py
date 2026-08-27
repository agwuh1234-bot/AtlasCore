from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class BrowserSessionError(RuntimeError):
    pass


class BrowserSessionStore:
    """Encrypted Playwright storage-state store.

    Auth state can contain cookies/tokens capable of impersonating the account, so
    plaintext state is never committed or returned through normal job responses.
    Encryption key must come from ATLAS_BROWSER_SESSION_KEY in the runtime secret store.
    """

    _NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")

    def __init__(self, root: str | None = None, key: str | None = None) -> None:
        self.root = Path(root or os.environ.get("ATLAS_BROWSER_SESSION_DIR", "/data/atlas-browser-sessions"))
        self.root.mkdir(parents=True, exist_ok=True)
        if self.root.is_symlink():
            raise BrowserSessionError("Session directory must not be a symlink")
        if not self.root.is_dir():
            raise BrowserSessionError("Session directory is invalid")
        os.chmod(self.root, 0o700)
        raw_key = key or os.environ.get("ATLAS_BROWSER_SESSION_KEY", "")
        if not raw_key:
            raise BrowserSessionError("ATLAS_BROWSER_SESSION_KEY is required")
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode("utf-8")).digest())
        self.cipher = Fernet(derived)

    @classmethod
    def _safe_name(cls, name: str) -> str:
        normalized = name.lower().strip()
        # Reject rather than silently rewriting input. This prevents two different
        # caller-provided names (or traversal-like strings) from aliasing one file.
        if not cls._NAME_RE.fullmatch(normalized):
            raise BrowserSessionError("Invalid session name")
        return normalized

    def _path(self, name: str) -> Path:
        return self.root / f"{self._safe_name(name)}.state.enc"

    @staticmethod
    def _reject_symlink(path: Path) -> None:
        if path.is_symlink():
            raise BrowserSessionError("Session path must not be a symlink")

    @staticmethod
    def _restrict_file_permissions(path: Path) -> None:
        os.chmod(path, 0o600)

    def exists(self, name: str) -> bool:
        path = self._path(name)
        self._reject_symlink(path)
        return path.is_file()

    def save(self, name: str, state: dict[str, Any]) -> None:
        payload = json.dumps(state, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        path = self._path(name)
        self._reject_symlink(path)
        encrypted = self.cipher.encrypt(payload)
        fd = -1
        tmp_path: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=self.root)
            tmp_path = Path(tmp_name)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb", closefd=True) as handle:
                fd = -1
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
            tmp_path = None
            self._restrict_file_permissions(path)
        finally:
            if fd >= 0:
                os.close(fd)
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except FileNotFoundError:
                    pass

    def load(self, name: str) -> dict[str, Any]:
        path = self._path(name)
        self._reject_symlink(path)
        if not path.is_file():
            raise BrowserSessionError("Session not found")
        self._restrict_file_permissions(path)
        try:
            raw = self.cipher.decrypt(path.read_bytes())
            value = json.loads(raw.decode("utf-8"))
        except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
            raise BrowserSessionError("Session state is invalid or cannot be decrypted") from exc
        if not isinstance(value, dict):
            raise BrowserSessionError("Session state has invalid format")
        return value

    def delete(self, name: str) -> bool:
        path = self._path(name)
        self._reject_symlink(path)
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_names(self) -> list[str]:
        names: list[str] = []
        for path in self.root.glob("*.state.enc"):
            if path.is_symlink() or not path.is_file():
                continue
            names.append(path.name.removesuffix(".state.enc"))
        return sorted(names)
