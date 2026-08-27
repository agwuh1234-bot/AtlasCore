import unittest

from atlas_n8n_ecom_repair import plan_safe_ecom_repair


def edge(node, index=0):
    return {"node": node, "type": "main", "index": index}


def workflow():
    return {
        "nodes": [
            {"name": "When clicking ‘Execute workflow’", "type": "n8n-nodes-base.manualTrigger", "disabled": False},
            {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "disabled": False},
            {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
            {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
            {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True},
        ],
        "connections": {
            "When clicking ‘Execute workflow’": {"main": [[edge("Shopify Build Brief", 1)]]},
            "Shopify Build Brief": {"main": [[edge("Message a model1")]]},
            "Message a model1": {"main": [[edge("Message a model")]]},
            "Message a model": {"main": [[edge("Edit a file")]]},
        },
    }


class RepairShapeGateTests(unittest.TestCase):
    def test_nonzero_target_input_index_blocks_all_repairs(self):
        plan = plan_safe_ecom_repair(workflow())
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn(
            "unsupported_connection_edge_index:When clicking ‘Execute workflow’:1",
            plan["remaining_issues"],
        )

    def test_malformed_nodes_collection_blocks_all_repairs(self):
        body = workflow()
        body["nodes"] = {"unexpected": "mapping"}
        plan = plan_safe_ecom_repair(body)
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn("malformed_nodes", plan["remaining_issues"])


if __name__ == "__main__":
    unittest.main()
