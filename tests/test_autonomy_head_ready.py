import unittest
from pathlib import Path


class HeadReadyTests(unittest.TestCase):
    def test_ready(self):
        self.assertEqual(Path("AUTONOMY_HEAD_READY").read_text().strip(), "READY")


if __name__ == "__main__":
    unittest.main()
