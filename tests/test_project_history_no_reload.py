import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProjectHistoryNoReloadTests(unittest.TestCase):
    def test_passive_history_hydration_never_reloads_document(self):
        source = (ROOT / 'web' / 'projects.js').read_text(encoding='utf-8')
        start = source.index('async function hydrateHistory()')
        end = source.index('\n\n  installUi();', start)
        hydrate = source[start:end]
        self.assertNotIn('window.location.reload()', hydrate)
        self.assertIn("atlas-history-hydrated", hydrate)
        self.assertIn('window.__ATLAS_PENDING_HISTORY', hydrate)

    def test_explicit_project_switch_keeps_reload_boundary(self):
        source = (ROOT / 'web' / 'projects.js').read_text(encoding='utf-8')
        start = source.index('function setActiveProject(id)')
        end = source.index('\n\n  function showError', start)
        switch = source[start:end]
        self.assertIn('window.location.reload()', switch)


if __name__ == '__main__':
    unittest.main()
