import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
LOGIN_JS = (WEB / "login.js").read_text(encoding="utf-8")
SAFE_HTML = (WEB / "safe.html").read_text(encoding="utf-8")
SAFE_JS = (WEB / "safe.js").read_text(encoding="utf-8")


class SafeModeEntrypointTests(unittest.TestCase):
    def test_authenticated_login_routes_to_safe_mode(self):
        self.assertIn("window.location.replace('/app/safe.html?login='", LOGIN_JS)

    def test_safe_mode_assets_are_wired(self):
        self.assertTrue((WEB / "safe.css").is_file())
        self.assertTrue((WEB / "safe.js").is_file())
        self.assertIn('/app/safe.css', SAFE_HTML)
        self.assertIn('/app/safe.js', SAFE_HTML)

    def test_safe_mode_is_read_only_by_default(self):
        self.assertIn('allow_writes:false', SAFE_JS)
        self.assertIn('claude_review:false', SAFE_JS)

    def test_safe_mode_requires_authenticated_session(self):
        self.assertIn("fetch('/app-session?safe='", SAFE_JS)
        self.assertIn("credentials:'same-origin'", SAFE_JS)
        self.assertIn("location.replace('/app/login.html?v='", SAFE_JS)

    def test_safe_mode_health_probe_bypasses_cache(self):
        self.assertIn("fetch('/health?safe='", SAFE_JS)
        self.assertIn("cache:'no-store'", SAFE_JS)


if __name__ == "__main__":
    unittest.main()
