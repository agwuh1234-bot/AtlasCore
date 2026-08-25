import unittest
from pathlib import Path


class ProgressTests(unittest.TestCase):
    def test_progress_keeps_ci_before_merge_and_shopify_last(self):
        text = Path("AUTONOMY_PROGRESS.md").read_text(encoding="utf-8")
        self.assertLess(text.index("Observe all CI"), text.index("Merge to `main`"))
        self.assertLess(text.index("read-only canary"), text.index("authenticated Shopify"))


if __name__ == "__main__":
    unittest.main()
