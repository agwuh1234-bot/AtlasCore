import os
import stat
import tempfile
import unittest
from pathlib import Path

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

    def test_root_permissions_are_restricted(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "sessions"
            root.mkdir(mode=0o777)
            os.chmod(root, 0o777)
            BrowserSessionStore(root=str(root), key="test-key")
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)

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

    def test_list_names_skips_symlinks(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            store = BrowserSessionStore(root=root, key="test-key")
            store.save("safe", {"cookies": [], "origins": []})
            target = Path(outside) / "external.state.enc"
            target.write_bytes(b"external")
            os.symlink(target, Path(root) / "linked.state.enc")
            self.assertEqual(store.list_names(), ["safe"])


if __name__ == "__main__":
    unittest.main()
