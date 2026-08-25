import unittest
from pathlib import Path


class BranchLockTests(unittest.TestCase):
    def test_branch_discipline_requires_pr_and_second_green_pass(self):
        text = Path("AUTONOMY_BRANCH_LOCK.md").read_text(encoding="utf-8")
        self.assertIn("Use a PR", text)
        self.assertIn("second green pass", text)
        self.assertIn("before merge", text)


if __name__ == "__main__":
    unittest.main()
