import os
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
