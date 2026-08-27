import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from atlas_browser_sessions import BrowserSessionError, BrowserSessionStore


class BrowserSessionExistsRaceTests(unittest.TestCase):
    def test_exists_rejects_last_moment_symlink_swap(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            store = BrowserSessionStore(root=root, key="test-key")
            store.save("shopify", {"cookies": [], "origins": []})
            path = store._path("shopify")
            target = Path(outside) / "outside.enc"
            target.write_bytes(path.read_bytes())
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
                    store.exists("shopify")

            self.assertTrue(swapped)

    def test_list_names_skips_last_moment_symlink_swap(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            store = BrowserSessionStore(root=root, key="test-key")
            store.save("safe", {"cookies": [], "origins": []})
            path = store._path("safe")
            target = Path(outside) / "outside.enc"
            target.write_bytes(path.read_bytes())
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
                self.assertEqual(store.list_names(), [])

            self.assertTrue(swapped)


if __name__ == "__main__":
    unittest.main()
