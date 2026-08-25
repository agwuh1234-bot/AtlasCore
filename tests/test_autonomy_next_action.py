import unittest
from pathlib import Path


class NextActionTests(unittest.TestCase):
    def test_next_action_is_pr_ci(self):
        self.assertEqual(Path("AUTONOMY_NEXT_ACTION.txt").read_text().strip(), "OPEN_PULL_REQUEST_AND_WAIT_FOR_CI")


if __name__ == "__main__":
    unittest.main()
