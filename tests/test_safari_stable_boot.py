import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SafariStableBootTests(unittest.TestCase):
    def test_heavy_features_are_lazy_but_paths_stay_wired(self):
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('src="/app/lazy-runtime.js"', html)
        for asset in (
            '/app/code-studio-live.js',
            '/app/video-studio-live.js',
            '/app/shopify-studio-live.js',
            '/app/automation-studio-live.js',
            '/app/file-studio-live.js',
            '/app/tools-center.js',
            '/app/templates-center.js',
            '/app/integrations-center.js',
            '/app/settings-center.js',
        ):
            marker = f'src="{asset}" type="application/atlas-lazy"'
            self.assertIn(marker, html)

    def test_lazy_runtime_loads_features_on_demand(self):
        source = (ROOT / 'web' / 'lazy-runtime.js').read_text(encoding='utf-8')
        self.assertIn('loadGroup', source)
        self.assertIn('application/atlas-lazy', source)
        self.assertIn('enableStyle', source)
        self.assertIn("window.AtlasLazy", source)

    def test_runtime_is_fail_soft_and_does_not_reload_loop(self):
        runtime = (ROOT / 'web' / 'runtime-refresh.js').read_text(encoding='utf-8')
        app = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')
        self.assertIn('revealCore', runtime)
        self.assertIn('removeAtlasWorkers', runtime)
        self.assertIn('/app-session?atlas_boot=', runtime)
        self.assertNotIn('controllerchange', runtime)
        self.assertNotIn('serviceWorker.register', runtime)
        self.assertNotIn('serviceWorker.register', app)

    def test_worker_cleanup_is_manual_only_during_normal_boot(self):
        runtime = (ROOT / 'web' / 'runtime-refresh.js').read_text(encoding='utf-8')
        start = runtime.index('function boot()')
        end = runtime.index("document.readyState==='loading'", start)
        boot = runtime[start:end]
        self.assertNotIn('removeAtlasWorkers()', boot)
        self.assertNotIn('cleanupStarted', boot)
        self.assertNotIn('2200', boot)
        self.assertIn('removeAtlasWorkers', runtime)

    def test_background_resume_does_not_repeat_worker_cleanup_or_leak_guards(self):
        runtime = (ROOT / 'web' / 'runtime-refresh.js').read_text(encoding='utf-8')
        self.assertIn("window.addEventListener('pagehide'", runtime)
        self.assertIn('stopHealthLoop()', runtime)
        self.assertIn('pageshow-bfcache', runtime)
        self.assertIn('dataset.atlasLoginGuard', runtime)
        self.assertIn('cleanupStarted', runtime)
        self.assertNotIn("pageshow',()=>{installLoginGuard();void health();void removeAtlasWorkers()", runtime)

    def test_diagnostic_mode_traces_safari_lifecycle(self):
        telemetry = (ROOT / 'web' / 'client-telemetry.js').read_text(encoding='utf-8')
        self.assertIn("lifecycle.pagehide", telemetry)
        self.assertIn("lifecycle.pageshow", telemetry)
        self.assertIn("lifecycle.hidden", telemetry)
        self.assertIn("lifecycle.visible", telemetry)

    def test_feature_styles_remain_lazy_until_opened(self):
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        loader = (ROOT / 'web' / 'style-loader.js').read_text(encoding='utf-8')
        self.assertIn('data-atlas-lazy-style', html)
        self.assertIn("hasAttribute('data-atlas-lazy-style')", loader)


if __name__ == '__main__':
    unittest.main()
