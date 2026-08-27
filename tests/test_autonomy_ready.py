import unittest
from pathlib import Path


class ReadyTests(unittest.TestCase):
    def test_marker_requires_green_ci(self):
        text = Path("AUTONOMY_READY").read_text(encoding="utf-8")
        self.assertIn("READY_FOR_PR_VALIDATION", text)
        self.assertIn("NOT_READY_FOR_PRODUCTION_UNTIL_GREEN_CI", text)


if __name__ == "__main__":
    unittest.main()
