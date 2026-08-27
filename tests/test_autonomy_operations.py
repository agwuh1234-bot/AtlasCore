import unittest
from pathlib import Path


class OperationsTests(unittest.TestCase):
    def test_first_canary_is_read_only_and_recovery_is_verified(self):
        text = Path("AUTONOMY_OPERATIONS.md").read_text(encoding="utf-8")
        self.assertIn("harmless public URL", text)
        self.assertIn("read-only", text)
        self.assertIn("controlled restart", text)
        self.assertIn("Shopify", text)


if __name__ == "__main__":
    unittest.main()
