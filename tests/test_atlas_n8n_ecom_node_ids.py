import unittest

from atlas_n8n_ecom_repair import plan_safe_ecom_repair


def edge(node):
    return {"node": node, "type": "main", "index": 0}


def workflow(nodes):
    return {
        "nodes": nodes,
        "connections": {
            "When clicking ‘Execute workflow’": {"main": [[edge("Shopify Build Brief")]]},
            "Shopify Build Brief": {"main": [[edge("Message a model1")]]},
            "Message a model1": {"main": [[edge("Message a model")]]},
            "Message a model": {"main": [[edge("Edit a file")]]},
        },
    }


class WorkflowNodeIdSafetyTests(unittest.TestCase):
    def base_nodes(self):
        return [
            {"id": "trigger-1", "name": "When clicking ‘Execute workflow’", "type": "n8n-nodes-base.manualTrigger", "disabled": False},
            {"id": "brief-1", "name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "disabled": False},
            {"id": "model-1", "name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
            {"id": "model-2", "name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
            {"id": "github-1", "name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True},
        ]

    def test_duplicate_node_id_blocks_all_repairs(self):
        nodes = self.base_nodes()
        nodes[-1]["id"] = "model-2"
        plan = plan_safe_ecom_repair(workflow(nodes))
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn("duplicate_workflow_node_id:model-2", plan["remaining_issues"])

    def test_blank_declared_node_id_blocks_all_repairs(self):
        nodes = self.base_nodes()
        nodes[-1]["id"] = "   "
        plan = plan_safe_ecom_repair(workflow(nodes))
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn("malformed_workflow_node_id:Edit a file", plan["remaining_issues"])

    def test_omitted_node_id_remains_supported(self):
        nodes = self.base_nodes()
        for node in nodes:
            node.pop("id")
        plan = plan_safe_ecom_repair(workflow(nodes))
        self.assertNotIn("malformed_workflow_node_id:Edit a file", plan["remaining_issues"])


if __name__ == "__main__":
    unittest.main()
