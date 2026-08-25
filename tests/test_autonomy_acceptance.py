import unittest
from pathlib import Path


class AcceptanceTests(unittest.TestCase):
    def test_acceptance_covers_concurrency_retry_recovery_and_canary(self):
        text = Path("AUTONOMY_ACCEPTANCE.md").read_text(encoding="utf-8")
        for term in ("concurrently", "retry", "approval", "PostgreSQL", "Chromium", "/health", "Railway restart", "Shopify"):
            self.assertIn(term, text)


if __name__ == "__main__":
    unittest.main()
