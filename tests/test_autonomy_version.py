import unittest
from pathlib import Path


class VersionTests(unittest.TestCase):
    def test_version_is_lifecycle_gated(self):
        self.assertEqual(Path("AUTONOMY_VERSION").read_text().strip(), "0.1.0-lifecycle-gated")


if __name__ == "__main__":
    unittest.main()
