import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from atlas_browser_sessions import BrowserSessionError, BrowserSessionStore


class BrowserSessionRootSecurityTests(unittest.TestCase):
    def test_root_validation_rejects_last_moment_symlink_swap_without_chmod_target(self):
        with tempfile.TemporaryDirectory() as parent, tempfile.TemporaryDirectory() as outside:
            root = Path(parent) / "sessions"
            root.mkdir()
            target = Path(outside)
            os.chmod(target, 0o755)
            real_open = os.open
            swapped = False

            def swap_then_open(candidate, flags, *args, **kwargs):
                nonlocal swapped
                if Path(candidate) == root and not swapped:
                    swapped = True
                    root.rmdir()
                    os.symlink(target, root, target_is_directory=True)
                return real_open(candidate, flags, *args, **kwargs)

            with mock.patch("atlas_browser_sessions.os.open", side_effect=swap_then_open):
                with self.assertRaises(BrowserSessionError):
                    BrowserSessionStore(root=str(root), key="test-key")

            self.assertTrue(swapped)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)

    def test_root_permissions_are_applied_to_opened_directory_inode(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "sessions"
            root.mkdir(mode=0o777)
            os.chmod(root, 0o777)
            BrowserSessionStore(root=str(root), key="test-key")
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)


if __name__ == "__main__":
    unittest.main()
