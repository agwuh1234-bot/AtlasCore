import unittest
from pathlib import Path


class HandoffTests(unittest.TestCase):
    def test_handoff_points_to_checkpoint_and_canary(self):
        text = Path("AUTONOMY_HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("do not rebuild", text)
        self.assertIn("AUTONOMY_CHECKPOINT.json", text)
        self.assertIn("AUTONOMY_CANARY.json", text)
        self.assertIn("green CI", text)


if __name__ == "__main__":
    unittest.main()
