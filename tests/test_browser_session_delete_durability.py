import tempfile
import unittest
from unittest import mock

from atlas_browser_sessions import BrowserSessionStore


class BrowserSessionDeleteDurabilityTests(unittest.TestCase):
    def test_delete_fsyncs_session_directory_after_unlink(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            store.save("shopify", {"cookies": [], "origins": []})

            with mock.patch.object(store, "_fsync_root_directory") as sync_root:
                self.assertTrue(store.delete("shopify"))

            sync_root.assert_called_once_with()
            self.assertFalse(store._path("shopify").exists())

    def test_missing_session_does_not_fsync_directory(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")

            with mock.patch.object(store, "_fsync_root_directory") as sync_root:
                self.assertFalse(store.delete("missing"))

            sync_root.assert_not_called()


if __name__ == "__main__":
    unittest.main()
