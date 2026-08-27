import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
INDEX = WEB / "index.html"


class FrontendAssetIntegrityTests(unittest.TestCase):
    def test_all_local_app_assets_referenced_by_index_exist(self):
        html = INDEX.read_text(encoding="utf-8")
        refs = re.findall(r'(?:href|src)="(/app/[^"?#]+)', html)
        self.assertTrue(refs, "index.html should reference local /app assets")

        missing = []
        for ref in sorted(set(refs)):
            relative = ref.removeprefix("/app/")
            if not (WEB / relative).is_file():
                missing.append(ref)

        self.assertEqual([], missing, f"Missing frontend assets referenced by index.html: {missing}")

    def test_ui_actions_assets_are_both_loaded(self):
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn('href="/app/ui-actions.css"', html)
        self.assertIn('src="/app/ui-actions.js"', html)


if __name__ == "__main__":
    unittest.main()
