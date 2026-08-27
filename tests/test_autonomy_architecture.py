import unittest
from pathlib import Path


class ArchitectureTests(unittest.TestCase):
    def test_architecture_records_core_invariants(self):
        text = Path("AUTONOMY_ARCHITECTURE.md").read_text(encoding="utf-8")
        for invariant in ("PostgreSQL", "bounded", "FastAPI", "encrypted", "independently"):
            self.assertIn(invariant, text)


if __name__ == "__main__":
    unittest.main()
