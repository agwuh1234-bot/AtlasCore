import unittest
from pathlib import Path


class RolloutTests(unittest.TestCase):
    def test_rollout_requires_health_and_recovery_checks(self):
        text = Path("AUTONOMY_ROLLOUT.md").read_text(encoding="utf-8")
        self.assertIn("/health.autonomy.started == true", text)
        self.assertIn("unfinished graph recovery", text)
        self.assertIn("Rollback", text)


if __name__ == "__main__":
    unittest.main()
