import unittest
from pathlib import Path


class PRBodyTests(unittest.TestCase):
    def test_pr_body_mentions_rollout_and_rollback(self):
        text = Path("AUTONOMY_PR_BODY.md").read_text(encoding="utf-8")
        self.assertIn("Rollout safety", text)
        self.assertIn("green CI", text)
        self.assertIn("Rollback", text)
        self.assertIn("Shopify", text)


if __name__ == "__main__":
    unittest.main()
