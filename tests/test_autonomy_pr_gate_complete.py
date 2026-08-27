import unittest
from pathlib import Path


class PRGateCompleteTests(unittest.TestCase):
    def test_gate_complete_marker(self):
        self.assertEqual(Path("AUTONOMY_PR_GATE_COMPLETE").read_text().strip(), "TRUE")


if __name__ == "__main__":
    unittest.main()
