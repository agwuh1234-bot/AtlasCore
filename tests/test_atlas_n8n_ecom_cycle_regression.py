import unittest

import atlas_n8n_ecom as ecom


class CyclicEcomTopologyRegressionTests(unittest.TestCase):
    def _base_workflow(self):
        return {
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

    def test_safe_cycle_does_not_hang_or_create_false_unsafe_node(self):
        workflow = self._base_workflow()
        workflow["connections"]["Message a model"] = {
            "main": [[{"node": "Message a model1", "type": "main", "index": 0}]]
        }

        safety = ecom._workflow_safety_summary(workflow)

        self.assertTrue(safety["ready_for_safe_manual_run"])
        self.assertEqual(safety["issues"], [])

    def test_cycle_that_reaches_disabled_legacy_write_node_is_blocked(self):
        workflow = self._base_workflow()
        workflow["connections"]["Message a model"] = {
            "main": [[
                {"node": "Message a model1", "type": "main", "index": 0},
                {"node": "Edit a file", "type": "main", "index": 0},
            ]]
        }
        workflow["connections"]["Edit a file"] = {
            "main": [[{"node": "Message a model1", "type": "main", "index": 0}]]
        }

        safety = ecom._workflow_safety_summary(workflow)

        self.assertFalse(safety["ready_for_safe_manual_run"])
        self.assertIn("unsafe_connection:Message a model->Edit a file", safety["issues"])
        self.assertIn("unexpected_reachable_node:Edit a file", safety["issues"])


if __name__ == "__main__":
    unittest.main()
