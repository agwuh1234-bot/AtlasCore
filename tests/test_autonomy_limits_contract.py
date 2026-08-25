import unittest
from pathlib import Path


class LimitsContractTests(unittest.TestCase):
    def test_limits_remain_bounded(self):
        text = Path("AUTONOMY_LIMITS.md").read_text(encoding="utf-8")
        self.assertIn("1..10", text)
        self.assertIn("5..300 seconds", text)
        self.assertIn("should not be removed", text)


if __name__ == "__main__":
    unittest.main()
