import unittest
from pathlib import Path


class NextGateTests(unittest.TestCase):
    def test_next_step_requires_ci_before_merge(self):
        text = Path("AUTONOMY_NEXT.md").read_text(encoding="utf-8")
        self.assertIn("PR", text)
        self.assertIn("If green", text)
        self.assertIn("Do not bypass", text)


if __name__ == "__main__":
    unittest.main()
