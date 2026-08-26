import unittest

from atlas_safe_logging import sanitize_for_log


class PrivateKeyLoggingTests(unittest.TestCase):
    def test_pem_private_key_is_redacted_from_free_form_log_text(self):
        private_key = (
            "-----BEGIN PRIVATE KEY-----\n"
            "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC1234567890\n"
            "abcdef0123456789abcdef0123456789abcdef0123456789\n"
            "-----END PRIVATE KEY-----"
        )
        safe = sanitize_for_log({"error": f"provider failed with key:\n{private_key}\nretry=false"})
        rendered = str(safe)
        self.assertNotIn("MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSj", rendered)
        self.assertNotIn("-----BEGIN PRIVATE KEY-----", rendered)
        self.assertIn("<redacted-private-key>", safe["error"])
        self.assertIn("retry=false", safe["error"])

    def test_rsa_private_key_variant_is_redacted(self):
        private_key = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA1234567890abcdef1234567890abcdef\n"
            "-----END RSA PRIVATE KEY-----"
        )
        safe = sanitize_for_log(f"trace={private_key}")
        self.assertEqual(safe, "trace=<redacted-private-key>")


if __name__ == "__main__":
    unittest.main()
