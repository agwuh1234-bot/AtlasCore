import os
import stat
import tempfile
import unittest
from pathlib import Path

from atlas_browser_executor import BrowserExecutor, BrowserExecutorError


class BrowserArtifactSecurityTests(unittest.TestCase):
    def test_artifact_directory_permissions_are_restricted(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "artifacts"
            root.mkdir(mode=0o777)
            os.chmod(root, 0o777)
            BrowserExecutor(artifact_dir=str(root))
            self.assertEqual(stat.S_IMODE(root.stat().st_mode), 0o700)

    def test_symlinked_artifact_directory_is_rejected_without_touching_target(self):
        with tempfile.TemporaryDirectory() as parent, tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "target"
            target.mkdir(mode=0o755)
            os.chmod(target, 0o755)
            linked = Path(parent) / "artifacts"
            os.symlink(target, linked)

            with self.assertRaises(BrowserExecutorError):
                BrowserExecutor(artifact_dir=str(linked))

            self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o755)


if __name__ == "__main__":
    unittest.main()
