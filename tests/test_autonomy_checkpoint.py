import json
import unittest
from pathlib import Path


class CheckpointTests(unittest.TestCase):
    def test_checkpoint_has_next_gate(self):
        data = json.loads(Path("AUTONOMY_CHECKPOINT.json").read_text(encoding="utf-8"))
        self.assertEqual(data["stage"], "lifecycle-integration-gated")
        self.assertIn("CI", data["next"])
        self.assertGreaterEqual(len(data["components"]), 10)


if __name__ == "__main__":
    unittest.main()
