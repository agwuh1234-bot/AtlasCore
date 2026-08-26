import unittest

import atlas_n8n_ecom as ecom


class MalformedEcomTopologyTests(unittest.TestCase):
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

    def test_non_mapping_connections_fail_closed_without_crashing(self):
        workflow = self._base_workflow()
        workflow["connections"] = []

        safety = ecom._workflow_safety_summary(workflow)

        self.assertFalse(safety["ready_for_safe_manual_run"])
        self.assertIn(
            "missing_connection:When clicking ‘Execute workflow’->Shopify Build Brief",
            safety["issues"],
        )
        self.assertIn(
            "missing_connection:Shopify Build Brief->Message a model1",
            safety["issues"],
        )
        self.assertIn(
            "missing_connection:Message a model1->Message a model",
            safety["issues"],
        )

    def test_malformed_branch_entries_fail_closed_without_crashing(self):
        workflow = self._base_workflow()
        workflow["connections"]["Shopify Build Brief"] = {
            "main": ["not-a-branch", None, [{"node": "Message a model1", "type": "main", "index": 0}]]
        }

        safety = ecom._workflow_safety_summary(workflow)

        self.assertTrue(safety["ready_for_safe_manual_run"])
        self.assertEqual(safety["issues"], [])

    def test_missing_connections_key_fails_closed(self):
        workflow = self._base_workflow()
        workflow.pop("connections")

        safety = ecom._workflow_safety_summary(workflow)

        self.assertFalse(safety["ready_for_safe_manual_run"])
        self.assertTrue(any(issue.startswith("missing_node:") for issue in safety["issues"]))


if __name__ == "__main__":
    unittest.main()
