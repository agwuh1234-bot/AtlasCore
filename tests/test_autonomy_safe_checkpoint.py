import unittest
from pathlib import Path


class SafeCheckpointTests(unittest.TestCase):
    def test_checkpoint_uses_branch_head_not_stale_sha(self):
        text = Path("AUTONOMY_LAST_SAFE_COMMIT.txt").read_text(encoding="utf-8")
        self.assertIn("branch head", text)
        self.assertIn("authoritative safe checkpoint", text)


if __name__ == "__main__":
    unittest.main()
