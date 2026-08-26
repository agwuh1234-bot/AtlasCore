import unittest

from atlas_n8n_ecom_repair import plan_safe_ecom_repair


def edge(node):
    return {"node": node, "type": "main", "index": 0}


class DuplicateWorkflowNodeNameTests(unittest.TestCase):
    def test_duplicate_legacy_target_name_blocks_all_repair_writes(self):
        value = {
            "nodes": [
                {"name": "When clicking ‘Execute workflow’", "type": "n8n-nodes-base.manualTrigger", "disabled": False},
                {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "disabled": False},
                {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
                {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
                {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True},
                {"name": "Edit a file", "type": "n8n-nodes-base.noOp", "disabled": True},
            ],
            "connections": {
                "When clicking ‘Execute workflow’": {"main": [[edge("Shopify Build Brief")]]},
                "Shopify Build Brief": {"main": [[edge("Message a model1")]]},
                "Message a model1": {"main": [[edge("Message a model")]]},
                "Message a model": {"main": [[edge("Edit a file")]]},
            },
        }

        plan = plan_safe_ecom_repair(value)

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn("duplicate_workflow_node_name:Edit a file", plan["remaining_issues"])

    def test_duplicate_disconnected_node_name_still_blocks_repair(self):
        value = {
            "nodes": [
                {"name": "When clicking ‘Execute workflow’", "type": "n8n-nodes-base.manualTrigger", "disabled": False},
                {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "disabled": False},
                {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
                {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
                {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True},
                {"name": "Detached", "type": "n8n-nodes-base.noOp", "disabled": True},
                {"name": "Detached", "type": "n8n-nodes-base.noOp", "disabled": True},
            ],
            "connections": {
                "When clicking ‘Execute workflow’": {"main": [[edge("Shopify Build Brief")]]},
                "Shopify Build Brief": {"main": [[edge("Message a model1")]]},
                "Message a model1": {"main": [[edge("Message a model")]]},
                "Message a model": {"main": [[edge("Edit a file")]]},
            },
        }

        plan = plan_safe_ecom_repair(value)

        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn("duplicate_workflow_node_name:Detached", plan["remaining_issues"])


if __name__ == "__main__":
    unittest.main()
