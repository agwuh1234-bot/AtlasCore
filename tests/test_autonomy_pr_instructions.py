import unittest
from pathlib import Path


class PRInstructionsTests(unittest.TestCase):
    def test_pr_targets_main_and_forbids_pre_ci_merge(self):
        text = Path("AUTONOMY_PR_INSTRUCTIONS.txt").read_text(encoding="utf-8")
        self.assertIn("HEAD=atlas/autonomy-lifecycle", text)
        self.assertIn("BASE=main", text)
        self.assertIn("MERGE_BEFORE_CI=false", text)


if __name__ == "__main__":
    unittest.main()
