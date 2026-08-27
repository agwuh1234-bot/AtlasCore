import unittest
from pathlib import Path


class FinalPrePRTests(unittest.TestCase):
    def test_checkpoint_identifies_ci_as_next_evidence(self):
        text = Path("AUTONOMY_FINAL_PRE_PR.md").read_text(encoding="utf-8")
        self.assertIn("Opening the PR", text)
        self.assertIn("CI results", text)
        self.assertIn("reduce safety", text)


if __name__ == "__main__":
    unittest.main()
