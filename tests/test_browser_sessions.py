import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from atlas_browser_sessions import BrowserSessionError, BrowserSessionStore


class BrowserSessionStoreTests(unittest.TestCase):
    def test_encrypted_roundtrip_and_delete(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-secret-with-enough-entropy")
            state = {"cookies": [{"name": "sid", "value": "secret-cookie"}], "origins": []}
            store.save("shopify", state)
            self.assertTrue(store.exists("shopify"))
            raw = (store._path("shopify")).read_bytes()
            self.assertNotIn(b"secret-cookie", raw)
            self.assertEqual(store.load("shopify"), state)
            self.assertIn("shopify", store.list_names())
            self.assertTrue(store.delete("shopify"))
            self.assertFalse(store.exists("shopify"))

    def test_delete_uses_nofollow_existence_check(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            store.save("shopify", {"cookies": [], "origins": []})
            with mock.patch.object(Path, "exists", side_effect=AssertionError("Path.exists must not be used")):
                self.assertTrue(store.delete("shopify"))
            self.assertFalse(store.exists("shopify"))

    def test_root_permissions_are_restricted(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "sessions"
            root.mkdir(mode=0o777)
            os.chmod(root, 0o777)
            BrowserSessionStore(root=str(root), key="test-key")
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)

    def test_rejects_symlinked_session_root(self):
        with tempfile.TemporaryDirectory() as parent, tempfile.TemporaryDirectory() as outside:
            root = Path(parent) / "sessions"
            os.symlink(outside, root)
            with self.assertRaisesRegex(BrowserSessionError, "cannot be opened safely"):
                BrowserSessionStore(root=str(root), key="test-key")

    def test_saved_session_permissions_are_restricted(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            store.save("shopify", {"cookies": [], "origins": []})
            self.assertEqual(stat.S_IMODE(store._path("shopify").stat().st_mode), 0o600)

    def test_load_repairs_permissive_session_permissions(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            state = {"cookies": [], "origins": []}
            store.save("shopify", state)
            path = store._path("shopify")
            os.chmod(path, 0o644)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o644)
            self.assertEqual(store.load("shopify"), state)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_wrong_key_cannot_decrypt(self):
        with tempfile.TemporaryDirectory() as root:
            BrowserSessionStore(root=root, key="key-one").save("shopify", {"cookies": [], "origins": []})
            with self.assertRaises(BrowserSessionError):
                BrowserSessionStore(root=root, key="key-two").load("shopify")

    def test_rejects_unsafe_session_name(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            with self.assertRaises(BrowserSessionError):
                store.exists("../shopify")

    def test_rejects_symlinked_session_file(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            store = BrowserSessionStore(root=root, key="test-key")
            target = Path(outside) / "outside.enc"
            target.write_bytes(b"do-not-touch")
            os.symlink(target, store._path("shopify"))
            with self.assertRaises(BrowserSessionError):
                store.exists("shopify")
            with self.assertRaises(BrowserSessionError):
                store.save("shopify", {"cookies": [], "origins": []})
            with self.assertRaises(BrowserSessionError):
                store.load("shopify")
            with self.assertRaises(BrowserSessionError):
                store.delete("shopify")
            self.assertEqual(target.read_bytes(), b"do-not-touch")

    def test_load_rejects_last_moment_symlink_swap(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            store = BrowserSessionStore(root=root, key="test-key")
            state = {"cookies": [], "origins": []}
            store.save("shopify", state)
            path = store._path("shopify")
            target = Path(outside) / "outside.enc"
            target.write_bytes(path.read_bytes())
            os.chmod(target, 0o644)
            real_open = os.open
            swapped = False

            def swap_then_open(candidate, flags, *args, **kwargs):
                nonlocal swapped
                if Path(candidate) == path and not swapped:
                    swapped = True
                    path.unlink()
                    os.symlink(target, path)
                return real_open(candidate, flags, *args, **kwargs)

            with mock.patch("atlas_browser_sessions.os.open", side_effect=swap_then_open):
                with self.assertRaises(BrowserSessionError):
                    store.load("shopify")

            self.assertTrue(swapped)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_list_names_skips_symlinks(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            store = BrowserSessionStore(root=root, key="test-key")
            store.save("safe", {"cookies": [], "origins": []})
            target = Path(outside) / "external.state.enc"
            target.write_bytes(b"external")
            os.symlink(target, Path(root) / "linked.state.enc")
            self.assertEqual(store.list_names(), ["safe"])

    def test_rejects_hardlinked_session_file_without_touching_external_inode(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            store = BrowserSessionStore(root=root, key="test-key")
            target = Path(outside) / "outside.enc"
            target.write_bytes(b"do-not-touch")
            os.chmod(target, 0o644)
            os.link(target, store._path("shopify"))

            with self.assertRaises(BrowserSessionError):
                store.exists("shopify")
            with self.assertRaises(BrowserSessionError):
                store.save("shopify", {"cookies": [], "origins": []})
            with self.assertRaises(BrowserSessionError):
                store.load("shopify")
            with self.assertRaises(BrowserSessionError):
                store.delete("shopify")

            self.assertEqual(target.read_bytes(), b"do-not-touch")
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o644)

    def test_list_names_skips_hardlinks(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            store = BrowserSessionStore(root=root, key="test-key")
            store.save("safe", {"cookies": [], "origins": []})
            target = Path(outside) / "external.state.enc"
            target.write_bytes(b"external")
            os.link(target, Path(root) / "linked.state.enc")
            self.assertEqual(store.list_names(), ["safe"])

    def test_save_rejects_oversized_plaintext_before_writing(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            store._MAX_PLAINTEXT_BYTES = 64
            with self.assertRaisesRegex(BrowserSessionError, "too large"):
                store.save("shopify", {"cookies": [], "blob": "x" * 128})
            self.assertFalse(store._path("shopify").exists())

    def test_load_rejects_oversized_encrypted_file_before_reading(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            store._MAX_ENCRYPTED_BYTES = 32
            path = store._path("shopify")
            path.write_bytes(b"x" * 33)
            with mock.patch("atlas_browser_sessions.os.fdopen") as fdopen:
                with self.assertRaisesRegex(BrowserSessionError, "too large"):
                    store.load("shopify")
            fdopen.assert_not_called()

    def test_load_rejects_decrypted_payload_over_plaintext_limit(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            payload = b'{"blob":"' + (b"x" * 128) + b'"}'
            encrypted = store.cipher.encrypt(payload)
            store._path("shopify").write_bytes(encrypted)
            store._MAX_PLAINTEXT_BYTES = 64
            store._MAX_ENCRYPTED_BYTES = len(encrypted) + 1
            with self.assertRaisesRegex(BrowserSessionError, "too large"):
                store.load("shopify")

    def test_save_rejects_non_finite_numbers_before_writing(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            for invalid in (float("nan"), float("inf"), float("-inf")):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(BrowserSessionError, "valid JSON"):
                        store.save("shopify", {"cookies": [], "origins": [], "value": invalid})
                    self.assertFalse(store._path("shopify").exists())

    def test_save_wraps_non_json_serializable_state(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            with self.assertRaisesRegex(BrowserSessionError, "valid JSON"):
                store.save("shopify", {"cookies": [], "origins": [], "value": object()})
            self.assertFalse(store._path("shopify").exists())


if __name__ == "__main__":
    unittest.main()
