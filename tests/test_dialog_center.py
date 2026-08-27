import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AtlasDialogCenterTests(unittest.TestCase):
    def test_dialog_assets_are_loaded_by_app_shell(self):
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/dialog-center.css', index)
        self.assertIn('/app/dialog-center.js', index)
        self.assertLess(index.index('/app/dialog-center.js'), index.index('/app/app.js'))

    def test_dialog_center_exposes_confirm_prompt_and_focus_trap(self):
        source = (ROOT / "web" / "dialog-center.js").read_text(encoding="utf-8")
        self.assertIn('window.AtlasDialog=', source)
        self.assertIn('confirm:confirmDialog', source)
        self.assertIn('prompt:promptDialog', source)
        self.assertIn("e.key==='Escape'", source)
        self.assertIn("e.key==='Tab'", source)
        self.assertIn("aria-modal", source)

    def test_dialog_styles_keep_mobile_safe_area_support(self):
        css = (ROOT / "web" / "dialog-center.css").read_text(encoding="utf-8")
        self.assertIn('env(safe-area-inset-bottom)', css)
        self.assertIn('@media(max-width:520px)', css)
        self.assertIn('prefers-reduced-motion', css)


if __name__ == '__main__':
    unittest.main()
