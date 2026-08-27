import unittest

from atlas_n8n_ecom_repair import plan_safe_ecom_repair


def edge(node):
    return {"node": node, "type": "main", "index": 0}


class LiveEcomRepairPlanTests(unittest.TestCase):
    def test_current_live_topology_allows_only_legacy_github_edge_removal(self):
        workflow = {
            "id": "0S8720gc3G2OODmG",
            "name": "ecomSX222",
            "active": False,
            "nodes": [
                {"name": "When clicking ‘Execute workflow’", "type": "n8n-nodes-base.manualTrigger", "disabled": False},
                {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "disabled": False},
                {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
                {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
                {"name": "HTTP Request", "type": "n8n-nodes-base.httpRequest", "disabled": True},
                {"name": "HTTP Request1", "type": "n8n-nodes-base.httpRequest", "disabled": True},
                {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True},
                {"name": "Sticky Note", "type": "n8n-nodes-base.stickyNote", "disabled": False},
            ],
            "connections": {
                "When clicking ‘Execute workflow’": {"main": [[edge("Shopify Build Brief")]]},
                "Shopify Build Brief": {"main": [[edge("Message a model1")]]},
                "Message a model1": {"main": [[edge("Message a model")]]},
                "Message a model": {"main": [[edge("Edit a file")]]},
            },
        }

        plan = plan_safe_ecom_repair(workflow)

        self.assertTrue(plan["ok"])
        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["remaining_issues"], [])
        self.assertEqual(
            plan["operations"],
            [
                {
                    "type": "removeConnection",
                    "source": "Message a model",
                    "target": "Edit a file",
                    "ignoreErrors": False,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
