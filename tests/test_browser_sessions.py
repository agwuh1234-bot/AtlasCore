import tempfile
import unittest

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


if __name__ == "__main__":
    unittest.main()
