import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from atlas_browser_sessions import BrowserSessionStore


class BrowserSessionSaveRaceTests(unittest.TestCase):
    def test_save_does_not_chmod_final_path_after_atomic_replace(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            store = BrowserSessionStore(root=root, key="test-key")
            final_path = store._path("shopify")
            outside_path = Path(outside) / "outside.enc"
            outside_path.write_bytes(b"do-not-touch")
            os.chmod(outside_path, 0o644)

            real_replace = os.replace

            def replace_then_swap(src, dst):
                real_replace(src, dst)
                Path(dst).unlink()
                os.symlink(outside_path, dst)

            with mock.patch("atlas_browser_sessions.os.replace", side_effect=replace_then_swap):
                store.save("shopify", {"cookies": [], "origins": []})

            self.assertTrue(final_path.is_symlink())
            self.assertEqual(outside_path.read_bytes(), b"do-not-touch")
            self.assertEqual(stat.S_IMODE(outside_path.stat().st_mode), 0o644)


if __name__ == "__main__":
    unittest.main()
