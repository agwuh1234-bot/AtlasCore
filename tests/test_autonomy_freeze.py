import unittest
from pathlib import Path


class FreezeTests(unittest.TestCase):
    def test_freeze_marker_waits_for_pr_ci(self):
        self.assertEqual(Path("AUTONOMY_NO_MORE_PRE_PR_EDITS").read_text().strip(), "FREEZE_UNTIL_PR_CI")


if __name__ == "__main__":
    unittest.main()
