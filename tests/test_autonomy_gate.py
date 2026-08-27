import unittest
from pathlib import Path


class GateTests(unittest.TestCase):
    def test_gate_requires_pr_validation(self):
        self.assertEqual(Path("AUTONOMY_GATE").read_text().strip(), "PR_VALIDATION_REQUIRED")


if __name__ == "__main__":
    unittest.main()
