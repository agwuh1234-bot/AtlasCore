import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "main.py").read_text(encoding="utf-8")
INDEX = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
RUNTIME_REFRESH = (ROOT / "web" / "runtime-refresh.js").read_text(encoding="utf-8")
SERVICE_WORKER = (ROOT / "web" / "sw.js").read_text(encoding="utf-8")


class AppEntrypointAvailabilityTests(unittest.TestCase):
    def test_root_serves_the_real_app_shell(self):
        self.assertIn('@api.get("/", include_in_schema=False)', MAIN)
        self.assertIn('FileResponse("web/index.html")', MAIN)

    def test_shell_keeps_critical_boot_assets(self):
        for asset in (
            '/app/styles.css',
            '/app/app.js',
            '/app/runtime-refresh.js',
        ):
            self.assertIn(asset, INDEX)

    def test_runtime_health_probe_bypasses_cache(self):
        self.assertIn("fetch('/health?atlas_refresh='", RUNTIME_REFRESH)
        self.assertIn("cache:'no-store'", RUNTIME_REFRESH)

    def test_service_worker_never_caches_health(self):
        self.assertIn("pathname === '/health'", SERVICE_WORKER)
        self.assertIn("fetchFresh(event.request)", SERVICE_WORKER)

    def test_service_worker_keeps_login_entrypoint_network_fresh(self):
        for path in (
            "pathname === '/login'",
            "pathname === '/app/login.js'",
            "pathname === '/app/login.css'",
        ):
            self.assertIn(path, SERVICE_WORKER)
        self.assertIn("isAuthEntrypoint(url.pathname)", SERVICE_WORKER)
        self.assertIn("event.respondWith(fetchFresh(event.request))", SERVICE_WORKER)


if __name__ == "__main__":
    unittest.main()
