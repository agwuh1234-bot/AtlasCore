import unittest
from pathlib import Path


class FinalCheckpointTests(unittest.TestCase):
    def test_sealed_checkpoint_points_to_pr_ci(self):
        text = Path("AUTONOMY_CHECKPOINT_FINAL.txt").read_text(encoding="utf-8")
        self.assertIn("SEALED_PRE_PR_CHECKPOINT", text)
        self.assertIn("NEXT=PR_CI", text)


if __name__ == "__main__":
    unittest.main()
