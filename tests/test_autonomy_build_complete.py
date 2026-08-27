import unittest
from pathlib import Path


class BuildCompleteTests(unittest.TestCase):
    def test_marker(self):
        self.assertEqual(Path("AUTONOMY_BUILD_COMPLETE").read_text().strip(), "PRE_PR_BUILD_PHASE_COMPLETE")


if __name__ == "__main__":
    unittest.main()
