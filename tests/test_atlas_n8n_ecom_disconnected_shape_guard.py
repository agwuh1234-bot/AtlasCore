import unittest

from atlas_n8n_ecom_repair import plan_safe_ecom_repair


TRIGGER = "When clicking ‘Execute workflow’"


def safe_workflow():
    return {
        "nodes": [
            {"name": TRIGGER, "type": "n8n-nodes-base.manualTrigger", "disabled": False},
            {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "disabled": False},
            {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
            {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
            {"name": "HTTP Request", "type": "n8n-nodes-base.httpRequest", "disabled": True},
            {"name": "HTTP Request1", "type": "n8n-nodes-base.httpRequest", "disabled": True},
            {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True},
        ],
        "connections": {
            TRIGGER: {"main": [[{"node": "Shopify Build Brief", "type": "main", "index": 0}]]},
            "Shopify Build Brief": {"main": [[{"node": "Message a model1", "type": "main", "index": 0}]]},
            "Message a model1": {"main": [[{"node": "Message a model", "type": "main", "index": 0}]]},
        },
    }


class DisconnectedShapeGuardTests(unittest.TestCase):
    def test_disconnected_non_main_connection_still_blocks_repair(self):
        workflow = safe_workflow()
        workflow["connections"]["HTTP Request1"] = {
            "ai_tool": [[{"node": "HTTP Request", "type": "ai_tool", "index": 0}]]
        }

        plan = plan_safe_ecom_repair(workflow)

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn(
            "unsupported_connection_output_type:HTTP Request1:ai_tool",
            plan["remaining_issues"],
        )

    def test_disconnected_edge_metadata_still_blocks_repair(self):
        workflow = safe_workflow()
        workflow["connections"]["HTTP Request1"] = {
            "main": [[{
                "node": "HTTP Request",
                "type": "main",
                "index": 0,
                "futureFlag": True,
            }]]
        }

        plan = plan_safe_ecom_repair(workflow)

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn(
            "unsupported_connection_edge_metadata:HTTP Request1:futureFlag",
            plan["remaining_issues"],
        )


if __name__ == "__main__":
    unittest.main()
