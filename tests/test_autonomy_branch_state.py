import json
import unittest
from pathlib import Path


class BranchStateTests(unittest.TestCase):
    def test_branch_is_ready_for_pr_not_production(self):
        data = json.loads(Path("AUTONOMY_BRANCH_STATE.json").read_text())
        self.assertEqual(data["state"], "ready_for_pr")
        self.assertFalse(data["production_wired"])
        self.assertTrue(data["ci_required"])


if __name__ == "__main__":
    unittest.main()
