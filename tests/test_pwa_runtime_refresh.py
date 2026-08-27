import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PwaRuntimeRefreshTests(unittest.TestCase):
    def test_service_worker_is_fresh_and_never_mutates_job_permissions(self):
        source = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")
        self.assertIn("atlas-app-v21-20260827", source)
        self.assertIn("cache: 'no-store'", source)
        self.assertIn("pathname === '/health'", source)
        self.assertIn("pathname.startsWith('/app-')", source)
        self.assertIn("self.skipWaiting()", source)
        self.assertIn("self.clients.claim()", source)
        self.assertNotIn("body.allow_writes = true", source)
        self.assertNotIn("body.allow_writes=true", source)

    def test_runtime_registers_root_worker_and_cleans_legacy_app_scope(self):
        source = (ROOT / "web" / "runtime-refresh.js").read_text(encoding="utf-8")
        self.assertIn("scope:'/'", source)
        self.assertIn("updateViaCache:'none'", source)
        self.assertIn("getRegistrations", source)
        self.assertIn("scopePath==='/app/'", source)
        self.assertIn("reg.unregister()", source)
        self.assertIn("controllerchange", source)
        self.assertIn("/health?atlas_refresh=", source)
        self.assertIn("cache:'no-store'", source)

    def test_server_prevents_stale_shell_and_allows_root_worker_scope(self):
        source = (ROOT / "atlas_app.py").read_text(encoding="utf-8")
        self.assertIn('"/app/sw.js"', source)
        self.assertIn('response.headers["Service-Worker-Allowed"] = "/"', source)
        self.assertIn('"no-store, no-cache, must-revalidate, max-age=0"', source)
        self.assertIn('path.startswith("/app-")', source)

    def test_runtime_refresh_is_loaded_by_app_shell(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('/app/runtime-refresh.js', html)
        self.assertLess(html.index('/app/app.js'), html.index('/app/runtime-refresh.js'))


if __name__ == "__main__":
    unittest.main()
