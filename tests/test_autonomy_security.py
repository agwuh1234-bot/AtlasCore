import unittest
from pathlib import Path


class SecurityBoundaryTests(unittest.TestCase):
    def test_security_doc_requires_idempotency_and_secret_isolation(self):
        text = Path("AUTONOMY_SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("idempotent", text)
        self.assertIn("Never place credentials", text)
        self.assertIn("approval worker", text)
        self.assertIn("bounded", text)


if __name__ == "__main__":
    unittest.main()
