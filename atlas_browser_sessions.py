from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
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
    _MAX_PLAINTEXT_BYTES = 8 * 1024 * 1024
    _MAX_ENCRYPTED_BYTES = 12 * 1024 * 1024

    def __init__(self, root: str | None = None, key: str | None = None) -> None:
        self.root = Path(root or os.environ.get("ATLAS_BROWSER_SESSION_DIR", "/data/atlas-browser-sessions"))
        self.root.mkdir(parents=True, exist_ok=True)
        self._secure_root_permissions(self.root)
        raw_key = key or os.environ.get("ATLAS_BROWSER_SESSION_KEY", "")
        if not raw_key:
            raise BrowserSessionError("ATLAS_BROWSER_SESSION_KEY is required")
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode("utf-8")).digest())
        self.cipher = Fernet(derived)

    @staticmethod
    def _secure_root_permissions(path: Path) -> None:
        """Validate and chmod the exact directory inode without following symlinks."""
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory = getattr(os, "O_DIRECTORY", 0)
        if not nofollow or not directory:
            raise BrowserSessionError("Secure session directory validation is unavailable on this platform")
        try:
            fd = os.open(path, os.O_RDONLY | nofollow | directory)
        except OSError as exc:
            raise BrowserSessionError("Session directory cannot be opened safely") from exc
        try:
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode):
                raise BrowserSessionError("Session directory is invalid")
            os.fchmod(fd, 0o700)
        finally:
            os.close(fd)

    def _fsync_root_directory(self) -> None:
        """Persist directory metadata for completed atomic filesystem changes."""
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        directory = getattr(os, "O_DIRECTORY", 0)
        if not nofollow or not directory:
            raise BrowserSessionError("Secure session directory sync is unavailable on this platform")
        try:
            fd = os.open(self.root, os.O_RDONLY | nofollow | directory)
        except OSError as exc:
            raise BrowserSessionError("Session directory cannot be opened safely for sync") from exc
        try:
            info = os.fstat(fd)
            if not stat.S_ISDIR(info.st_mode):
                raise BrowserSessionError("Session directory is invalid")
            os.fsync(fd)
        except OSError as exc:
            raise BrowserSessionError("Session directory could not be synced") from exc
        finally:
            os.close(fd)

    @classmethod
    def _safe_name(cls, name: str) -> str:
        normalized = name.lower().strip()
        if not cls._NAME_RE.fullmatch(normalized):
            raise BrowserSessionError("Invalid session name")
        return normalized

    def _path(self, name: str) -> Path:
        return self.root / f"{self._safe_name(name)}.state.enc"

    @staticmethod
    def _reject_unsafe_existing_file(path: Path) -> None:
        if path.is_symlink():
            raise BrowserSessionError("Session path must not be a symlink")
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            return
        if not stat.S_ISREG(info.st_mode):
            raise BrowserSessionError("Session path must be a regular file")
        if info.st_nlink != 1:
            raise BrowserSessionError("Session path must not be hardlinked")

    @staticmethod
    def _safe_regular_file_exists(path: Path) -> bool:
        """Check existence on the exact inode without following a swapped symlink."""
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        if not nofollow:
            raise BrowserSessionError("Secure session existence checks are unavailable on this platform")
        try:
            fd = os.open(path, os.O_RDONLY | nofollow)
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise BrowserSessionError("Session path cannot be opened safely") from exc
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise BrowserSessionError("Session path must be a regular file")
            if info.st_nlink != 1:
                raise BrowserSessionError("Session path must not be hardlinked")
            return True
        finally:
            os.close(fd)

    def _open_session_for_read(self, path: Path) -> int:
        """Open a session without following a last-moment symlink swap."""
        flags = os.O_RDONLY
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        if not nofollow:
            raise BrowserSessionError("Secure session loading is unavailable on this platform")
        try:
            fd = os.open(path, flags | nofollow)
        except FileNotFoundError as exc:
            raise BrowserSessionError("Session not found") from exc
        except OSError as exc:
            raise BrowserSessionError("Session path cannot be opened safely") from exc
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode):
                raise BrowserSessionError("Session path must be a regular file")
            if info.st_nlink != 1:
                raise BrowserSessionError("Session path must not be hardlinked")
            if info.st_size > self._MAX_ENCRYPTED_BYTES:
                raise BrowserSessionError("Session state is too large")
            os.fchmod(fd, 0o600)
            return fd
        except Exception:
            os.close(fd)
            raise

    def exists(self, name: str) -> bool:
        return self._safe_regular_file_exists(self._path(name))

    def save(self, name: str, state: dict[str, Any]) -> None:
        payload = json.dumps(state, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if len(payload) > self._MAX_PLAINTEXT_BYTES:
            raise BrowserSessionError("Session state is too large")
        path = self._path(name)
        self._reject_unsafe_existing_file(path)
        encrypted = self.cipher.encrypt(payload)
        if len(encrypted) > self._MAX_ENCRYPTED_BYTES:
            raise BrowserSessionError("Encrypted session state is too large")
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
            self._fsync_root_directory()
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
        fd = self._open_session_for_read(path)
        try:
            with os.fdopen(fd, "rb", closefd=True) as handle:
                fd = -1
                encrypted = handle.read(self._MAX_ENCRYPTED_BYTES + 1)
            if len(encrypted) > self._MAX_ENCRYPTED_BYTES:
                raise BrowserSessionError("Session state is too large")
            raw = self.cipher.decrypt(encrypted)
            if len(raw) > self._MAX_PLAINTEXT_BYTES:
                raise BrowserSessionError("Session state is too large")
            value = json.loads(raw.decode("utf-8"))
        except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
            raise BrowserSessionError("Session state is invalid or cannot be decrypted") from exc
        finally:
            if fd >= 0:
                os.close(fd)
        if not isinstance(value, dict):
            raise BrowserSessionError("Session state has invalid format")
        return value

    def delete(self, name: str) -> bool:
        path = self._path(name)
        self._reject_unsafe_existing_file(path)
        if not self._safe_regular_file_exists(path):
            return False
        try:
            path.unlink()
        except FileNotFoundError:
            return False
        self._fsync_root_directory()
        return True

    def list_names(self) -> list[str]:
        names: list[str] = []
        for path in self.root.glob("*.state.enc"):
            name = path.name.removesuffix(".state.enc")
            try:
                if not self._safe_regular_file_exists(path):
                    continue
                self._safe_name(name)
            except BrowserSessionError:
                continue
            names.append(name)
        return sorted(names)
