import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import atlas_n8n_ecom as ecom


class AtlasN8NEcomTests(unittest.IsolatedAsyncioTestCase):
    def test_safe_params_never_exposes_credential_values(self):
        node = {
            "name": "HTTP Request",
            "type": "n8n-nodes-base.httpRequest",
            "parameters": {
                "method": "POST",
                "url": "https://example.test/api",
                "authentication": "predefinedCredentialType",
                "nodeCredentialType": "shopifyApi",
                "sendBody": True,
                "headers": {"Authorization": "Bearer super-secret"},
                "body": {"token": "super-secret"},
            },
            "credentials": {
                "shopifyApi": {"id": "cred-123", "name": "Production Shopify"}
            },
        }

        safe = ecom._safe_params(node)

        self.assertEqual(safe["method"], "POST")
        self.assertEqual(safe["url"], "https://example.test/api")
        self.assertNotIn("headers", safe)
        self.assertNotIn("body", safe)
        self.assertNotIn("super-secret", repr(safe))

    def test_safe_params_redacts_model_message_content(self):
        node = {
            "name": "Message a model",
            "type": "@n8n/n8n-nodes-langchain.anthropic",
            "parameters": {
                "modelId": "claude-test",
                "messages": {"values": [{"content": "token=super-secret"}]},
                "options": {"temperature": 0.2},
            },
        }

        safe = ecom._safe_params(node)

        self.assertEqual(safe["modelId"], "claude-test")
        self.assertEqual(safe["message_count"], 1)
        self.assertEqual(safe["option_keys"], ["temperature"])
        self.assertNotIn("super-secret", repr(safe))
        self.assertNotIn("messages", safe)

    def test_collect_nodes_exposes_only_credential_types(self):
        workflow = {
            "nodes": [
                {
                    "name": "HTTP Request",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4,
                    "parameters": {"method": "GET", "url": "https://example.test"},
                    "credentials": {
                        "shopifyApi": {"id": "cred-123", "name": "Production Shopify"}
                    },
                }
            ],
            "connections": {},
        }

        nodes = ecom._collect_nodes(workflow)

        self.assertEqual(nodes[0]["credential_types"], ["shopifyApi"])
        rendered = repr(nodes)
        self.assertNotIn("cred-123", rendered)
        self.assertNotIn("Production Shopify", rendered)

    def test_find_workflow_is_case_insensitive_and_requires_id(self):
        payload = {
            "data": [
                {"name": "ECOMSX222"},
                {"name": "EcomSX222", "id": "wf-1"},
            ]
        }
        self.assertEqual(ecom._find_workflow(payload, "ecomsx222")["id"], "wf-1")

    def test_has_connection_reads_n8n_main_topology(self):
        body = {
            "connections": {
                "Start": {
                    "main": [[{"node": "Shopify Build Brief", "type": "main", "index": 0}]]
                }
            }
        }

        self.assertTrue(ecom._has_connection(body, "Start", "Shopify Build Brief"))
        self.assertFalse(ecom._has_connection(body, "Start", "HTTP Request"))
        self.assertFalse(ecom._has_connection(body, "Missing", "Shopify Build Brief"))

    def test_add_connection_if_missing_repairs_topology(self):
        operations = []
        body = {"connections": {}}

        ecom._add_connection_if_missing(operations, body, "Start", "Shopify Build Brief")

        self.assertEqual(
            operations,
            [{"type": "addConnection", "source": "Start", "target": "Shopify Build Brief"}],
        )

    def test_add_connection_if_missing_is_idempotent(self):
        operations = []
        body = {
            "connections": {
                "Start": {
                    "main": [[{"node": "Shopify Build Brief", "type": "main", "index": 0}]]
                }
            }
        }

        ecom._add_connection_if_missing(operations, body, "Start", "Shopify Build Brief")

        self.assertEqual(operations, [])

    def test_workflow_safety_summary_marks_safe_topology_ready(self):
        workflow = {
            "nodes": [
                {"name": "When clicking ‘Execute workflow’", "type": "n8n-nodes-base.manualTrigger", "parameters": {}},
                {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "parameters": {}},
                {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "parameters": {}},
                {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "parameters": {}},
                {"name": "HTTP Request", "type": "n8n-nodes-base.httpRequest", "disabled": True, "parameters": {}},
                {"name": "HTTP Request1", "type": "n8n-nodes-base.httpRequest", "disabled": True, "parameters": {}},
                {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True, "parameters": {}},
            ],
            "connections": {
                "When clicking ‘Execute workflow’": {"main": [[{"node": "Shopify Build Brief", "type": "main", "index": 0}]]},
                "Shopify Build Brief": {"main": [[{"node": "Message a model1", "type": "main", "index": 0}]]},
                "Message a model1": {"main": [[{"node": "Message a model", "type": "main", "index": 0}]]},
            },
        }

        safety = ecom._workflow_safety_summary(workflow)

        self.assertTrue(safety["ready_for_safe_manual_run"])
        self.assertEqual(safety["issues"], [])

    def test_workflow_safety_summary_blocks_enabled_legacy_write_path(self):
        workflow = {
            "nodes": [
                {"name": "When clicking ‘Execute workflow’", "type": "n8n-nodes-base.manualTrigger", "parameters": {}},
                {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "parameters": {}},
                {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "parameters": {}},
                {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "parameters": {}},
                {"name": "HTTP Request", "type": "n8n-nodes-base.httpRequest", "disabled": False, "parameters": {}},
                {"name": "HTTP Request1", "type": "n8n-nodes-base.httpRequest", "disabled": True, "parameters": {}},
                {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": False, "parameters": {}},
            ],
            "connections": {
                "When clicking ‘Execute workflow’": {"main": [[
                    {"node": "Shopify Build Brief", "type": "main", "index": 0},
                    {"node": "HTTP Request", "type": "main", "index": 0},
                ]]},
                "Shopify Build Brief": {"main": [[{"node": "Message a model1", "type": "main", "index": 0}]]},
                "Message a model1": {"main": [[{"node": "Message a model", "type": "main", "index": 0}]]},
                "Message a model": {"main": [[{"node": "Edit a file", "type": "main", "index": 0}]]},
            },
        }

        safety = ecom._workflow_safety_summary(workflow)

        self.assertFalse(safety["ready_for_safe_manual_run"])
        self.assertIn("unsafe_node_enabled:HTTP Request", safety["issues"])
        self.assertIn("unsafe_node_enabled:Edit a file", safety["issues"])
        self.assertIn("unsafe_connection:When clicking ‘Execute workflow’->HTTP Request", safety["issues"])
        self.assertIn("unsafe_connection:Message a model->Edit a file", safety["issues"])

    async def test_upgrade_is_fail_closed_when_feature_flag_is_off(self):
        logger = MagicMock()
        with patch.dict(os.environ, {"N8N_UPGRADE_ECOMSX222_SHOPIFY": ""}, clear=False), \
             patch.object(ecom, "configured", return_value=True), \
             patch.object(ecom, "call_tool", new=AsyncMock()) as call_tool:
            await ecom.maybe_upgrade_ecomsx222_shopify(logger)

        call_tool.assert_not_awaited()

    async def test_upgrade_does_not_call_n8n_when_policy_blocks_write(self):
        logger = MagicMock()
        with patch.dict(os.environ, {"N8N_UPGRADE_ECOMSX222_SHOPIFY": "1"}, clear=False), \
             patch.object(ecom, "configured", return_value=True), \
             patch.object(ecom, "decision", return_value=(False, "writes_disabled")), \
             patch.object(ecom, "call_tool", new=AsyncMock()) as call_tool:
            await ecom.maybe_upgrade_ecomsx222_shopify(logger)

        call_tool.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
