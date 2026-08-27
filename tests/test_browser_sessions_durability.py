import os
import tempfile
import unittest
from unittest import mock

from atlas_browser_sessions import BrowserSessionError, BrowserSessionStore


class BrowserSessionDurabilityTests(unittest.TestCase):
    def test_save_fsyncs_session_directory_after_replace(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            real_fsync = os.fsync
            calls = []

            def tracking_fsync(fd):
                calls.append(fd)
                return real_fsync(fd)

            with mock.patch("atlas_browser_sessions.os.fsync", side_effect=tracking_fsync):
                store.save("shopify", {"cookies": [], "origins": []})

            self.assertGreaterEqual(len(calls), 2)
            self.assertEqual(store.load("shopify"), {"cookies": [], "origins": []})

    def test_directory_sync_failure_is_fail_closed(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            with mock.patch.object(store, "_fsync_root_directory", side_effect=BrowserSessionError("sync failed")):
                with self.assertRaisesRegex(BrowserSessionError, "sync failed"):
                    store.save("shopify", {"cookies": [], "origins": []})


if __name__ == "__main__":
    unittest.main()
