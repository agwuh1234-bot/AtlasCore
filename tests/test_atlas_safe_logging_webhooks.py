import unittest

from atlas_safe_logging import sanitize_for_log


class WebhookSecretLoggingTests(unittest.TestCase):
    def test_slack_webhook_path_is_redacted(self):
        secret_path = "T00000000/B00000000/abcdefghijklmnopqrstuvwxyz123456"
        value = f"https://hooks.slack.com/services/{secret_path}"
        safe = sanitize_for_log({"error": f"delivery failed at {value}"})
        rendered = str(safe)
        self.assertNotIn(secret_path, rendered)
        self.assertIn("https://hooks.slack.com/services/<redacted-webhook>", safe["error"])

    def test_discord_webhook_token_is_redacted(self):
        webhook_id = "123456789012345678"
        webhook_token = "abcdefghijklmnopqrstuvwxyz.ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        value = f"https://discord.com/api/webhooks/{webhook_id}/{webhook_token}"
        safe = sanitize_for_log({"note": f"discord response from {value}?wait=true"})
        rendered = str(safe)
        self.assertNotIn(webhook_id, rendered)
        self.assertNotIn(webhook_token, rendered)
        self.assertIn("https://discord.com/api/webhooks/<redacted-webhook>?wait=true", safe["note"])

    def test_benign_non_webhook_urls_are_preserved(self):
        value = "https://discord.com/api/v10/channels/123/messages"
        safe = sanitize_for_log({"url": value})
        self.assertEqual(safe["url"], value)


if __name__ == "__main__":
    unittest.main()
