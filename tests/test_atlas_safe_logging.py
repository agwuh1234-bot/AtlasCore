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
