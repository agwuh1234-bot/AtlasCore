import unittest
from pathlib import Path


class FinalPRBodyTests(unittest.TestCase):
    def test_final_body_has_ci_canary_and_rollback(self):
        text = Path("AUTONOMY_PR_BODY_FINAL.md").read_text(encoding="utf-8")
        self.assertIn("CI", text)
        self.assertIn("read-only browser canary", text)
        self.assertIn("Rollback", text)


if __name__ == "__main__":
    unittest.main()
