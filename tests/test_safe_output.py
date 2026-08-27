import unittest

from atlas_safe_output import bounded_tool_result, truncate_text


class SafeOutputTests(unittest.TestCase):
    def test_short_text_unchanged(self):
        text, truncated = truncate_text("abc", max_chars=10)
        self.assertEqual(text, "abc")
        self.assertFalse(truncated)

    def test_long_text_is_bounded_and_marked(self):
        text, truncated = truncate_text("abcdefghij", max_chars=4)
        self.assertTrue(truncated)
        self.assertTrue(text.startswith("abcd"))
        self.assertIn("6 chars omitted", text)

    def test_tool_result_reports_original_size(self):
        result = bounded_tool_result("abcdef", max_chars=3)
        self.assertEqual(result["content_chars"], 6)
        self.assertTrue(result["truncated"])


if __name__ == "__main__":
    unittest.main()
