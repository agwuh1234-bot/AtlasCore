import unittest
from pathlib import Path


class RecoveryContractTests(unittest.TestCase):
    def test_recovery_requires_worker_boundary_and_idempotency(self):
        text = Path("AUTONOMY_RECOVERY.md").read_text(encoding="utf-8")
        self.assertIn("worker boundary", text)
        self.assertIn("Completed steps stay completed", text)
        self.assertIn("idempotency", text)
        self.assertIn("read-only", text)


if __name__ == "__main__":
    unittest.main()
