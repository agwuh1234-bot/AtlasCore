import os
import tempfile
import unittest
from pathlib import Path

from atlas_knowledge import (
    MEMORY_POLICY,
    PERMISSION_LEVELS,
    SHOPIFY_PLAYBOOK,
    memory_candidates,
    plugin_registry,
    seed_project_knowledge,
    system_registry,
)
from atlas_store import AtlasStore


class AtlasKnowledgeTests(unittest.TestCase):
    def test_shopify_playbook_has_safety_and_mobile_rules(self):
        self.assertIn("Shopify Operator", SHOPIFY_PLAYBOOK)
        self.assertIn("mobile-first", SHOPIFY_PLAYBOOK)
        self.assertIn("подтверждения", SHOPIFY_PLAYBOOK)
        self.assertIn("draft/preview", SHOPIFY_PLAYBOOK)

    def test_memory_policy_rejects_secrets(self):
        self.assertTrue(memory_candidates("Моя цель — запустить магазин"))
        self.assertEqual(memory_candidates("Важно: API key sk-supersecret123456"), [])
        self.assertIn("Не сохраняй пароли", MEMORY_POLICY)

    def test_shopify_knowledge_seed_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = AtlasStore(
                database_url="",
                sqlite_path=str(Path(temp_dir) / "atlas.db"),
            )
            store.initialize()
            seed_project_knowledge(store)
            first = store.search_memories("project-shopify", "", 30)
            seed_project_knowledge(store)
            second = store.search_memories("project-shopify", "", 30)
            self.assertGreaterEqual(len(first), 4)
            self.assertEqual(len(first), len(second))
            store.close()

    def test_plugin_registry_exposes_shopify_brain_without_credentials(self):
        old_domain = os.environ.pop("SHOPIFY_STORE_DOMAIN", None)
        old_token = os.environ.pop("SHOPIFY_ADMIN_ACCESS_TOKEN", None)
        try:
            registry = {item["id"]: item for item in plugin_registry()}
            self.assertEqual(registry["shopify"]["status"], "knowledge-ready")
            self.assertTrue(registry["shopify"]["requires_confirmation"])
            self.assertEqual(registry["memory"]["status"], "connected")
            self.assertEqual(registry["files"]["status"], "connected")
            self.assertEqual(registry["push"]["status"], "available")
            self.assertEqual(registry["automations"]["status"], "connected")
            self.assertTrue(registry["files"]["requires_confirmation"])
        finally:
            if old_domain is not None:
                os.environ["SHOPIFY_STORE_DOMAIN"] = old_domain
            if old_token is not None:
                os.environ["SHOPIFY_ADMIN_ACCESS_TOKEN"] = old_token

    def test_system_registry_reports_required_services_without_secrets(self):
        registry = {item["id"]: item for item in system_registry("postgres")}
        self.assertTrue(registry["postgres"]["connected"])
        self.assertTrue(registry["web"]["connected"])
        self.assertIn("openai", registry)
        self.assertNotIn("token", str(registry).lower())

    def test_permission_levels_require_confirmation_for_writes(self):
        levels = {item["id"]: item for item in PERMISSION_LEVELS}
        self.assertTrue(levels["read"]["automatic"])
        self.assertTrue(levels["safe"]["automatic"])
        self.assertTrue(levels["write"]["confirmation"])
        self.assertTrue(levels["dangerous"]["confirmation"])


if __name__ == "__main__":
    unittest.main()
