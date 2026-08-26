from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SkillPackSafetyTests(unittest.TestCase):
    def _read(self, relative: str) -> str:
        path = ROOT / relative
        self.assertTrue(path.exists(), f"missing skill file: {relative}")
        text = path.read_text(encoding="utf-8")
        self.assertGreater(len(text.strip()), 50, f"skill file is unexpectedly empty: {relative}")
        return text.lower()

    def test_shopify_skill_keeps_publish_delete_and_secret_guards(self):
        text = self._read("skills/shopify/SKILL.md")
        self.assertIn("never expose shopify credentials", text)
        self.assertIn("never delete", text)
        self.assertIn("explicit approval", text)
        self.assertIn("never silently publish", text)
        self.assertIn("validate mutations after execution", text)

    def test_n8n_skill_keeps_inspect_idempotency_and_destructive_guards(self):
        text = self._read("skills/n8n/SKILL.md")
        self.assertIn("inspect the existing workflow before editing", text)
        self.assertIn("smallest safe change", text)
        self.assertIn("avoid duplicate nodes/actions", text)
        self.assertIn("never expose mcp/api tokens", text)
        self.assertIn("explicit approval", text)

    def test_ecommerce_orchestrator_keeps_review_boundary(self):
        text = self._read("skills/ecommerce-orchestrator/SKILL.md")
        self.assertIn("keep storefront unpublished until review", text)
        self.assertIn("reversible non-destructive changes", text)
        self.assertIn("publishing, deletion, irreversible changes", text)
        self.assertIn("require explicit approval", text)


if __name__ == "__main__":
    unittest.main()
