import unittest

from atlas_n8n_ecom_repair import plan_safe_ecom_repair


TRIGGER = "When clicking ‘Execute workflow’"


def workflow():
    return {
        "nodes": [
            {"name": TRIGGER, "type": "n8n-nodes-base.manualTrigger", "disabled": False},
            {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "disabled": False},
            {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
            {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
            {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True},
        ],
        "connections": {
            TRIGGER: {"main": [[{"node": "Shopify Build Brief", "type": "main", "index": 0}]]},
            "Shopify Build Brief": {"main": [[{"node": "Message a model1", "type": "main", "index": 0}]]},
            "Message a model1": {"main": [[{"node": "Message a model", "type": "main", "index": 0}]]},
        },
    }


class EcomMissingConnectionMetadataTests(unittest.TestCase):
    def test_missing_edge_type_blocks_repair(self):
        value = workflow()
        del value["connections"][TRIGGER]["main"][0][0]["type"]
        plan = plan_safe_ecom_repair(value)
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn(f"missing_connection_edge_type:{TRIGGER}", plan["remaining_issues"])

    def test_missing_edge_index_blocks_repair(self):
        value = workflow()
        del value["connections"][TRIGGER]["main"][0][0]["index"]
        plan = plan_safe_ecom_repair(value)
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertIn(f"missing_connection_edge_index:{TRIGGER}", plan["remaining_issues"])


if __name__ == "__main__":
    unittest.main()
