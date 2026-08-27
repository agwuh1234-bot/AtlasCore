import unittest

from atlas_n8n_ecom_repair import plan_safe_ecom_repair


class AtlasN8NEcomMalformedNodeTests(unittest.TestCase):
    def _workflow(self):
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

    def test_non_mapping_node_blocks_repair(self):
        workflow = self._workflow()
        workflow["nodes"].append("corrupt-node")

        plan = plan_safe_ecom_repair(workflow)

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn("malformed_workflow_node:7", plan["remaining_issues"])

    def test_missing_node_name_blocks_repair(self):
        workflow = self._workflow()
        workflow["nodes"].append({"type": "n8n-nodes-base.set", "parameters": {}})

        plan = plan_safe_ecom_repair(workflow)

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn("malformed_workflow_node_name:7", plan["remaining_issues"])


if __name__ == "__main__":
    unittest.main()
