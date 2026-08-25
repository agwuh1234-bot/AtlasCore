import unittest
from pathlib import Path


class SummaryTests(unittest.TestCase):
    def test_summary_points_to_ci_as_next_evidence(self):
        text = Path("AUTONOMY_SUMMARY.md").read_text(encoding="utf-8")
        self.assertIn("restart recovery", text)
        self.assertIn("FastAPI-loop-safe", text)
        self.assertIn("CI on a PR", text)


if __name__ == "__main__":
    unittest.main()
