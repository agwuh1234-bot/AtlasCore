import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AtlasDialogFocusTests(unittest.TestCase):
    def test_tab_returns_focus_inside_dialog_if_focus_escapes(self):
        source = (ROOT / 'web' / 'dialog-center.js').read_text(encoding='utf-8')
        self.assertIn('active=document.activeElement', source)
        self.assertIn('if(!panel.contains(active))', source)
        self.assertIn('(e.shiftKey?last:first).focus()', source)

    def test_focus_trap_still_wraps_first_and_last_controls(self):
        source = (ROOT / 'web' / 'dialog-center.js').read_text(encoding='utf-8')
        self.assertIn('e.shiftKey&&active===first', source)
        self.assertIn('!e.shiftKey&&active===last', source)
        self.assertIn('last.focus()', source)
        self.assertIn('first.focus()', source)


if __name__ == '__main__':
    unittest.main()
