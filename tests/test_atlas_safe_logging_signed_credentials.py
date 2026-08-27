import unittest

from atlas_safe_logging import sanitize_for_log


class SignedUrlCredentialLoggingTests(unittest.TestCase):
    def test_aws_presigned_credential_scope_is_redacted(self):
        url = (
            "https://example-bucket.s3.amazonaws.com/object?"
            "X-Amz-Credential=AKIAABCDEFGHIJKLMNOP/20260827/eu-central-1/s3/aws4_request&"
            "X-Amz-Signature=abcdef1234567890"
        )
        rendered = sanitize_for_log(url)
        self.assertIn("X-Amz-Credential=<redacted>", rendered)
        self.assertIn("X-Amz-Signature=<redacted>", rendered)
        self.assertNotIn("AKIAABCDEFGHIJKLMNOP", rendered)
        self.assertNotIn("abcdef1234567890", rendered)

    def test_google_signed_credential_scope_is_redacted(self):
        url = (
            "https://storage.googleapis.com/bucket/object?"
            "X-Goog-Credential=service-account%40example.iam.gserviceaccount.com/20260827/auto/storage/goog4_request&"
            "X-Goog-Signature=abcdef1234567890"
        )
        rendered = sanitize_for_log(url)
        self.assertIn("X-Goog-Credential=<redacted>", rendered)
        self.assertIn("X-Goog-Signature=<redacted>", rendered)
        self.assertNotIn("service-account%40example.iam.gserviceaccount.com", rendered)
        self.assertNotIn("abcdef1234567890", rendered)


if __name__ == "__main__":
    unittest.main()
