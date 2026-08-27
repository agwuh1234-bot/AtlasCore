import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class StableCoreRootTests(unittest.TestCase):
    def test_root_executes_only_core_assets_before_legacy_template(self):
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        before, marker, after = html.partition('<template id="atlas-legacy-regression-assets">')
        self.assertTrue(marker)
        self.assertIn('/app/core.css?v=20260827-core1', before)
        self.assertIn('/app/core.js?v=20260827-core1', before)
        self.assertNotIn('/app/runtime-refresh.js', before)
        self.assertNotIn('/app/app.js', before)
        self.assertNotIn('/app/dashboard.js', before)
        self.assertNotIn('/app/workspace.js', before)
        self.assertIn('/app/runtime-refresh.js', after)
        self.assertIn('/app/app.js', after)

    def test_core_chat_uses_real_jobs_and_claude_review(self):
        source = (ROOT / 'web' / 'core.js').read_text(encoding='utf-8')
        self.assertIn("'/app-jobs'", source)
        self.assertIn('claude_review:state.claude', source)
        self.assertIn('allow_writes:state.writes', source)
        self.assertIn("method:'DELETE'", source)
        self.assertNotIn('serviceWorker', source)
        self.assertNotIn('location.reload', source)

    def test_core_has_visible_static_shell_even_before_javascript(self):
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        before = html.split('<script src="/app/core.js', 1)[0]
        self.assertIn('<h1>Atlas</h1>', before)
        self.assertIn('Стабильное ядро готово к работе.', before)
        self.assertIn('id="messageInput"', before)
        self.assertIn('id="claudeBtn"', before)


if __name__ == '__main__':
    unittest.main()
