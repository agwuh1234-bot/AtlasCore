from __future__ import annotations

import base64
import hashlib
import json
import os
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

    def __init__(self, root: str | None = None, key: str | None = None) -> None:
        self.root = Path(root or os.environ.get("ATLAS_BROWSER_SESSION_DIR", "/data/atlas-browser-sessions"))
        self.root.mkdir(parents=True, exist_ok=True)
        raw_key = key or os.environ.get("ATLAS_BROWSER_SESSION_KEY", "")
        if not raw_key:
            raise BrowserSessionError("ATLAS_BROWSER_SESSION_KEY is required")
        # Accept an arbitrary high-entropy runtime secret and derive a valid Fernet key.
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode("utf-8")).digest())
        self.cipher = Fernet(derived)

    @staticmethod
    def _safe_name(name: str) -> str:
        cleaned = "".join(c for c in name.lower().strip() if c.isalnum() or c in "-_")
        if not cleaned or len(cleaned) > 80:
            raise BrowserSessionError("Invalid session name")
        return cleaned

    def _path(self, name: str) -> Path:
        return self.root / f"{self._safe_name(name)}.state.enc"

    def exists(self, name: str) -> bool:
        return self._path(name).is_file()

    def save(self, name: str, state: dict[str, Any]) -> None:
        payload = json.dumps(state, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        path = self._path(name)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(self.cipher.encrypt(payload))
        os.chmod(tmp, 0o600)
        tmp.replace(path)

    def load(self, name: str) -> dict[str, Any]:
        path = self._path(name)
        if not path.is_file():
            raise BrowserSessionError("Session not found")
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
        if not path.exists():
            return False
        path.unlink()
        return True

    def list_names(self) -> list[str]:
        return sorted(p.name.removesuffix(".state.enc") for p in self.root.glob("*.state.enc"))
