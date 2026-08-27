import unittest
from pathlib import Path


class ReleaseNotesTests(unittest.TestCase):
    def test_release_notes_do_not_claim_premature_production_readiness(self):
        text = Path("AUTONOMY_RELEASE_NOTES.md").read_text(encoding="utf-8")
        self.assertIn("not marked production-ready yet", text)
        self.assertIn("read-only browser canary", text)
        self.assertIn("No authenticated Shopify", text)


if __name__ == "__main__":
    unittest.main()
