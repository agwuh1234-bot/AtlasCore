import unittest
from pathlib import Path


class StatusTests(unittest.TestCase):
    def test_status_does_not_claim_production_wiring_early(self):
        text = Path("AUTONOMY_STATUS.txt").read_text(encoding="utf-8")
        self.assertIn("PRODUCTION MAIN: NOT MODIFIED", text)
        self.assertIn("GREEN CI", text)
        self.assertIn("RAILWAY CANARY", text)


if __name__ == "__main__":
    unittest.main()
