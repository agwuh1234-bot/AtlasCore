import unittest
from pathlib import Path


class ChangelogTests(unittest.TestCase):
    def test_changelog_matches_version_and_core_features(self):
        text = Path("AUTONOMY_CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("0.1.0-lifecycle-gated", text)
        self.assertIn("PostgreSQL", text)
        self.assertIn("FastAPI", text)
        self.assertIn("fail-closed", text)


if __name__ == "__main__":
    unittest.main()
