import unittest

from atlas_safe_logging import compact_json_for_log, sanitize_for_log


class SafeLoggingTests(unittest.TestCase):
    def test_sensitive_keys_are_redacted_recursively(self):
        value = {
            "authorization": "Bearer secret",
            "nested": {
                "apiKey": "abc",
                "password": "pw",
                "safe": "ok",
            },
            "headers": {"X-Test": "secret"},
            "body": {"token": "secret"},
        }
        safe = sanitize_for_log(value)
        rendered = str(safe)
        self.assertNotIn("Bearer secret", rendered)
        self.assertNotIn("abc", rendered)
        self.assertNotIn("pw", rendered)
        self.assertIn("ok", rendered)
        self.assertEqual(safe["authorization"], "<redacted>")
        self.assertEqual(safe["headers"], "<redacted>")
        self.assertEqual(safe["body"], "<redacted>")

    def test_sensitive_key_variants_are_redacted(self):
        value = {
            "accessToken": "a",
            "client-secret": "b",
            "webhook_token": "c",
            "session.cookie": "d",
            "dbCredentials": "e",
            "tokenCount": 7,
            "secretary": "safe",
        }
        safe = sanitize_for_log(value)
        for key in ("accessToken", "client-secret", "webhook_token", "session.cookie", "dbCredentials"):
            self.assertEqual(safe[key], "<redacted>")
        self.assertEqual(safe["tokenCount"], 7)
        self.assertEqual(safe["secretary"], "safe")
        rendered = str(safe)
        for leaked in ("'a'", "'b'", "'c'", "'d'", "'e'"):
            self.assertNotIn(leaked, rendered)

    def test_embedded_auth_credentials_are_redacted_in_free_form_strings(self):
        safe = sanitize_for_log({
            "error": "upstream rejected Authorization: Bearer super-secret-token",
            "note": "proxy used Basic dXNlcjpwYXNz and failed",
        })
        rendered = str(safe)
        self.assertNotIn("super-secret-token", rendered)
        self.assertNotIn("dXNlcjpwYXNz", rendered)
        self.assertIn("Bearer <redacted>", safe["error"])
        self.assertIn("Basic <redacted>", safe["note"])

    def test_plaintext_credential_assignments_are_redacted(self):
        safe = sanitize_for_log({
            "error": "request failed token=tok-123 api_key: key-456 password='pw-789' mode=test",
            "note": 'refresh-token="refresh-abc" cookie=session-xyz status=failed',
        })
        rendered = str(safe)
        for leaked in ("tok-123", "key-456", "pw-789", "refresh-abc", "session-xyz"):
            self.assertNotIn(leaked, rendered)
        self.assertIn("token=<redacted>", safe["error"])
        self.assertIn("api_key: <redacted>", safe["error"])
        self.assertIn("password=<redacted>", safe["error"])
        self.assertIn("refresh-token=<redacted>", safe["note"])
        self.assertIn("cookie=<redacted>", safe["note"])
        self.assertIn("mode=test", safe["error"])
        self.assertIn("status=failed", safe["note"])

    def test_prefixed_credential_assignments_are_redacted_in_free_form_strings(self):
        safe = sanitize_for_log({
            "error": "webhook_token=hook-123 client-secret: sec-456 dbCredentials='db-789' mode=test",
            "url": "https://example.test/x?session_cookie=cookie-abc&service_token=tok-xyz&mode=test",
        })
        rendered = str(safe)
        for leaked in ("hook-123", "sec-456", "db-789", "cookie-abc", "tok-xyz"):
            self.assertNotIn(leaked, rendered)
        self.assertIn("webhook_token=<redacted>", safe["error"])
        self.assertIn("client-secret: <redacted>", safe["error"])
        self.assertIn("dbCredentials=<redacted>", safe["error"])
        self.assertIn("session_cookie=<redacted>", safe["url"])
        self.assertIn("service_token=<redacted>", safe["url"])
        self.assertIn("mode=test", safe["error"])
        self.assertIn("mode=test", safe["url"])

    def test_known_provider_secrets_are_redacted_without_labels(self):
        openai = "sk-1234567890abcdefghijklmnopqrstuv"
        anthropic = "sk-ant-1234567890abcdefghijklmnop"
        github = "ghp_1234567890abcdefghijklmnopqrstuv"
        github_pat = "github_pat_1234567890abcdefghijklmnopqrstuv"
        safe = sanitize_for_log({
            "error": f"provider failure {openai} {anthropic}",
            "note": f"github auth failed {github} and {github_pat}",
        })
        rendered = str(safe)
        for leaked in (openai, anthropic, github, github_pat):
            self.assertNotIn(leaked, rendered)
        self.assertEqual(safe["error"].count("<redacted-secret>"), 2)
        self.assertEqual(safe["note"].count("<redacted-secret>"), 2)

    def test_slack_and_stripe_secrets_are_redacted_without_labels(self):
        slack_bot = "xox" + "b-" + "123456789012-abcdefghijklmnopqrstuvwxyz"
        slack_app = "xox" + "a-" + "123456789012-abcdefghijklmnopqrstuvwxyz"
        stripe_secret = "sk_" + "live_" + "1234567890abcdefghijklmnop"
        stripe_restricted = "rk_" + "test_" + "1234567890abcdefghijklmnop"
        safe = sanitize_for_log({
            "error": f"slack failure {slack_bot} {slack_app}",
            "note": f"stripe failure {stripe_secret} {stripe_restricted}",
        })
        rendered = str(safe)
        for leaked in (slack_bot, slack_app, stripe_secret, stripe_restricted):
            self.assertNotIn(leaked, rendered)
        self.assertEqual(safe["error"].count("<redacted-secret>"), 2)
        self.assertEqual(safe["note"].count("<redacted-secret>"), 2)

    def test_sensitive_url_query_parameters_are_redacted(self):
        safe = sanitize_for_log({
            "url": "https://example.test/hook?token=secret-token&next=/ok&api_key=key-123",
            "error": "request failed at https://example.test/x?access_token=abc123&mode=test",
        })
        rendered = str(safe)
        for leaked in ("secret-token", "key-123", "abc123"):
            self.assertNotIn(leaked, rendered)
        self.assertIn("token=<redacted>", safe["url"])
        self.assertIn("api_key=<redacted>", safe["url"])
        self.assertIn("access_token=<redacted>", safe["error"])
        self.assertIn("next=/ok", safe["url"])
        self.assertIn("mode=test", safe["error"])

    def test_url_userinfo_credentials_are_redacted(self):
        safe = sanitize_for_log({
            "url": "https://atlas-user:super-secret@example.test/api",
            "error": "failed to reach postgres://dbuser:p%40ss@db.example.test:5432/app",
        })
        rendered = str(safe)
        for leaked in ("atlas-user", "super-secret", "dbuser", "p%40ss"):
            self.assertNotIn(leaked, rendered)
        self.assertEqual(safe["url"], "https://<redacted>@example.test/api")
        self.assertIn("postgres://<redacted>@db.example.test:5432/app", safe["error"])

    def test_standalone_jwt_like_tokens_are_redacted(self):
        token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.c2lnbmF0dXJlMTIz"
        safe = sanitize_for_log({
            "error": f"upstream returned session {token} during handshake",
            "note": "ordinary.version.string should remain visible",
        })
        rendered = str(safe)
        self.assertNotIn(token, rendered)
        self.assertIn("<redacted-jwt>", safe["error"])
        self.assertEqual(safe["note"], "ordinary.version.string should remain visible")

    def test_auth_scheme_values_are_redacted_fail_closed(self):
        safe = sanitize_for_log({"note": "Bearer authentication and Basic authentication are supported"})
        self.assertEqual(safe["note"], "Bearer <redacted> and Basic <redacted> are supported")

    def test_large_and_deep_payloads_are_bounded(self):
        value = {
            "items": list(range(100)),
            "deep": {"a": {"b": {"c": {"d": {"e": {"f": "secret"}}}}}},
        }
        safe = sanitize_for_log(value, max_depth=3, max_items=10)
        self.assertIn("<truncated_items:90>", str(safe))
        self.assertIn("<truncated>", str(safe))

    def test_long_strings_are_truncated(self):
        safe = sanitize_for_log({"note": "x" * 1000})
        self.assertLess(len(safe["note"]), 600)
        self.assertTrue(safe["note"].endswith("…<truncated>"))

    def test_compact_json_has_hard_character_cap(self):
        rendered = compact_json_for_log({"safe": "x" * 1000}, max_chars=120)
        self.assertLessEqual(len(rendered), 140)
        self.assertTrue(rendered.endswith("…<truncated>"))


if __name__ == "__main__":
    unittest.main()