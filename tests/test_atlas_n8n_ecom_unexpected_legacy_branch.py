import unittest

from atlas_n8n_ecom import _workflow_safety_summary


class EcomUnexpectedLegacyBranchTests(unittest.TestCase):
    def _workflow(self):
        trigger = "When clicking ‘Execute workflow’"
        return {
            "active": False,
            "nodes": [
                {"name": trigger, "type": "n8n-nodes-base.manualTrigger", "disabled": False, "parameters": {}},
                {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "disabled": False, "parameters": {}},
                {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False, "parameters": {}},
                {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False, "parameters": {}},
                {"name": "HTTP Request1", "type": "n8n-nodes-base.httpRequest", "disabled": True, "parameters": {}},
            ],
            "connections": {
                trigger: {"main": [[
                    {"node": "Shopify Build Brief", "type": "main", "index": 0},
                    {"node": "HTTP Request1", "type": "main", "index": 0},
                ]]},
                "Shopify Build Brief": {"main": [[{"node": "Message a model1", "type": "main", "index": 0}]]},
                "Message a model1": {"main": [[{"node": "Message a model", "type": "main", "index": 0}]]},
            },
        }

    def test_disabled_legacy_http_branch_is_still_blocked_when_reachable(self):
        summary = _workflow_safety_summary(self._workflow())

        self.assertFalse(summary["ready_for_safe_manual_run"])
        self.assertIn("unexpected_reachable_node:HTTP Request1", summary["issues"])

    def test_removing_legacy_branch_restores_safe_topology(self):
        workflow = self._workflow()
        workflow["connections"]["When clicking ‘Execute workflow’"]["main"][0] = [
            {"node": "Shopify Build Brief", "type": "main", "index": 0}
        ]

        summary = _workflow_safety_summary(workflow)

        self.assertTrue(summary["ready_for_safe_manual_run"])
        self.assertEqual([], summary["issues"])


if __name__ == "__main__":
    unittest.main()
