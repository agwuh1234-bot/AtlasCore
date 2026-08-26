import unittest

import atlas_n8n_ecom as ecom


class AtlasN8NEcomGraphSafetyTests(unittest.TestCase):
    def _safe_workflow(self):
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

    def test_safe_chain_contains_only_expected_reachable_nodes(self):
        workflow = self._safe_workflow()
        reachable = ecom._reachable_nodes(workflow, "When clicking ‘Execute workflow’")
        self.assertEqual(reachable, {"Shopify Build Brief", "Message a model1", "Message a model"})
        self.assertTrue(ecom._workflow_safety_summary(workflow)["ready_for_safe_manual_run"])

    def test_unknown_reachable_node_blocks_manual_run(self):
        workflow = self._safe_workflow()
        workflow["nodes"].append({"name": "Unexpected Writer", "type": "n8n-nodes-base.code", "parameters": {}})
        workflow["connections"]["Message a model"] = {
            "main": [[{"node": "Unexpected Writer", "type": "main", "index": 0}]]
        }

        safety = ecom._workflow_safety_summary(workflow)

        self.assertFalse(safety["ready_for_safe_manual_run"])
        self.assertIn("unexpected_reachable_node:Unexpected Writer", safety["issues"])

    def test_required_node_name_cannot_hide_wrong_type(self):
        workflow = self._safe_workflow()
        for node in workflow["nodes"]:
            if node["name"] == "Message a model":
                node["type"] = "n8n-nodes-base.github"
                break

        safety = ecom._workflow_safety_summary(workflow)

        self.assertFalse(safety["ready_for_safe_manual_run"])
        self.assertIn("unexpected_node_type:Message a model:n8n-nodes-base.github", safety["issues"])

    def test_duplicate_required_node_name_blocks_manual_run(self):
        workflow = self._safe_workflow()
        workflow["nodes"].append({
            "name": "Message a model1",
            "type": "@n8n/n8n-nodes-langchain.anthropic",
            "parameters": {},
        })

        safety = ecom._workflow_safety_summary(workflow)

        self.assertFalse(safety["ready_for_safe_manual_run"])
        self.assertIn("duplicate_node_name:Message a model1", safety["issues"])


if __name__ == "__main__":
    unittest.main()
