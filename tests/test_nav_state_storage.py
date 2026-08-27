import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class NavStateStorageTests(unittest.TestCase):
    def test_storage_read_is_guarded_and_chat_is_fallback(self):
        source = (ROOT / 'web' / 'nav-state.js').read_text(encoding='utf-8')
        self.assertIn("function storedTab(){try{return localStorage.getItem('atlas_active_tab')||''}catch(_){return''}}", source)
        self.assertIn("storedTab()||'chat'", source)
        self.assertNotIn("dataset.activeTab||localStorage.getItem('atlas_active_tab')", source)


if __name__ == '__main__':
    unittest.main()
