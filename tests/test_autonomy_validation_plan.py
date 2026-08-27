import unittest
from pathlib import Path


class ValidationPlanTests(unittest.TestCase):
    def test_plan_requires_real_source_validation_before_merge(self):
        text = Path("AUTONOMY_VALIDATION_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("temporary checkout", text)
        self.assertIn("real integrated source", text)
        self.assertIn("before merge", text)


if __name__ == "__main__":
    unittest.main()
