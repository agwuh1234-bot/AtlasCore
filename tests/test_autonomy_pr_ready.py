import unittest
from pathlib import Path


class PRReadyTests(unittest.TestCase):
    def test_pr_ready_marker(self):
        text = Path("AUTONOMY_PR_READY.txt").read_text(encoding="utf-8")
        self.assertIn("OPEN_PR_NOW", text)
        self.assertIn("HEAD_IS_SAFE_CHECKPOINT", text)


if __name__ == "__main__":
    unittest.main()
