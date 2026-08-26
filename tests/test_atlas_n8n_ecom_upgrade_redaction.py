import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import atlas_n8n_ecom


class EcomUpgradeRedactionTests(unittest.IsolatedAsyncioTestCase):
    async def test_upgrade_result_payload_is_not_logged(self):
        secret = "PRIVATE_UPDATE_RESULT token=do-not-log"
        trigger = "When clicking ‘Execute workflow’"
        workflow = {
            "nodes": [
                {"name": trigger, "type": "n8n-nodes-base.manualTrigger", "parameters": {}},
                {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "parameters": {}},
                {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "parameters": {}},
                {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "parameters": {}},
            ],
            "connections": {
                trigger: {"main": [[{"node": "Shopify Build Brief"}]]},
                "Shopify Build Brief": {"main": [[{"node": "Message a model1"}]]},
                "Message a model1": {"main": [[{"node": "Message a model"}]]},
            },
        }
        before = SimpleNamespace(structuredContent=workflow, content=[])
        update = SimpleNamespace(structuredContent={"echo": secret}, content=[])
        verify = SimpleNamespace(structuredContent=workflow, content=[])
        call_tool = AsyncMock(side_effect=[before, update, verify])
        logger = Mock()

        with patch.dict(os.environ, {"N8N_UPGRADE_ECOMSX222_SHOPIFY": "1"}, clear=False), \
             patch.object(atlas_n8n_ecom, "configured", return_value=True), \
             patch.object(atlas_n8n_ecom, "decision", return_value=(True, "allowed")), \
             patch.object(atlas_n8n_ecom, "call_tool", call_tool):
            await atlas_n8n_ecom.maybe_upgrade_ecomsx222_shopify(logger)

        rendered = repr(logger.info.call_args_list)
        self.assertNotIn(secret, rendered)
        self.assertNotIn("do-not-log", rendered)
        self.assertIn("update_result_present", rendered)
        self.assertNotIn('"update_result":', rendered)


if __name__ == "__main__":
    unittest.main()
