import os
import tempfile
import unittest
from unittest import mock

from atlas_browser_sessions import BrowserSessionError, BrowserSessionStore


class BrowserSessionBoundedReadTests(unittest.TestCase):
    def test_load_rechecks_encrypted_size_during_read(self):
        with tempfile.TemporaryDirectory() as root:
            store = BrowserSessionStore(root=root, key="test-key")
            store._MAX_ENCRYPTED_BYTES = 64
            path = store._path("shopify")
            path.write_bytes(b"x" * 65)

            # Model a file that passed the initial fstat size check and then grew
            # before load() actually read from the already-open descriptor.
            with mock.patch.object(
                store,
                "_open_session_for_read",
                side_effect=lambda candidate: os.open(candidate, os.O_RDONLY),
            ):
                with self.assertRaisesRegex(BrowserSessionError, "too large"):
                    store.load("shopify")


if __name__ == "__main__":
    unittest.main()
