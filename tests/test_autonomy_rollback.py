import unittest
from pathlib import Path


class RollbackTests(unittest.TestCase):
    def test_rollback_preserves_durable_state(self):
        text = Path("AUTONOMY_ROLLBACK.md").read_text(encoding="utf-8")
        self.assertIn("Leave `atlas_autonomous_tasks` rows untouched", text)
        self.assertIn("Do not delete encrypted browser sessions", text)
        self.assertIn("resume_all()", text)


if __name__ == "__main__":
    unittest.main()
