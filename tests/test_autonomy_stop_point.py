import unittest
from pathlib import Path


class StopPointTests(unittest.TestCase):
    def test_stop_point_is_validation_not_blocker(self):
        text = Path("AUTONOMY_STOP_POINT.md").read_text(encoding="utf-8")
        self.assertIn("not a development blocker", text)
        self.assertIn("opening the PR", text)
        self.assertIn("workflow results", text)


if __name__ == "__main__":
    unittest.main()
