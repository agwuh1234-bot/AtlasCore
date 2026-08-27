from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class UIActionsAccessibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "web" / "ui-actions.js").read_text(encoding="utf-8")

    def test_quick_menu_dialog_has_accessible_name(self):
        self.assertIn('aria-labelledby="atlas-action-modal-title"', self.source)
        self.assertIn('id="atlas-action-modal-title"', self.source)

    def test_quick_menu_supports_escape_close(self):
        self.assertIn("e.key==='Escape'", self.source)
        self.assertIn("e.preventDefault();closeModal()", self.source)

    def test_quick_menu_focuses_close_and_restores_previous_focus(self):
        self.assertIn("state.prevFocus=document.activeElement", self.source)
        self.assertIn("close.focus()", self.source)
        self.assertIn("document.contains(f)", self.source)
        self.assertIn("f.focus()", self.source)

    def test_quick_menu_traps_tab_focus_inside_dialog(self):
        self.assertIn("e.key==='Tab'", self.source)
        self.assertIn("const first=focusable[0],last=focusable[focusable.length-1]", self.source)
        self.assertIn("e.shiftKey&&document.activeElement===first", self.source)
        self.assertIn("!e.shiftKey&&document.activeElement===last", self.source)
        self.assertIn("last.focus()", self.source)
        self.assertIn("first.focus()", self.source)


if __name__ == "__main__":
    unittest.main()
