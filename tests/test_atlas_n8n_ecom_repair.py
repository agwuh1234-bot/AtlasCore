import unittest

from atlas_n8n_ecom_repair import plan_safe_ecom_repair


def workflow(connections):
    return {
        "nodes": [
            {"name": "When clicking ‘Execute workflow’", "type": "n8n-nodes-base.manualTrigger", "disabled": False},
            {"name": "Shopify Build Brief", "type": "n8n-nodes-base.set", "disabled": False},
            {"name": "Message a model1", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
            {"name": "Message a model", "type": "@n8n/n8n-nodes-langchain.anthropic", "disabled": False},
            {"name": "Edit a file", "type": "n8n-nodes-base.github", "disabled": True},
        ],
        "connections": connections,
    }


class EcomRepairPlannerTests(unittest.TestCase):
    def test_live_legacy_edge_produces_exact_remove_operation(self):
        value = workflow({
            "When clicking ‘Execute workflow’": {"main": [[{"node": "Shopify Build Brief"}]]},
            "Shopify Build Brief": {"main": [[{"node": "Message a model1"}]]},
            "Message a model1": {"main": [[{"node": "Message a model"}]]},
            "Message a model": {"main": [[{"node": "Edit a file"}]]},
        })
        plan = plan_safe_ecom_repair(value)
        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["remaining_issues"], [])
        self.assertEqual(plan["operations"], [{
            "type": "removeConnection",
            "source": "Message a model",
            "target": "Edit a file",
            "ignoreErrors": False,
        }])

    def test_missing_required_edge_is_planned_without_execution(self):
        value = workflow({
            "When clicking ‘Execute workflow’": {"main": [[{"node": "Shopify Build Brief"}]]},
            "Message a model1": {"main": [[{"node": "Message a model"}]]},
        })
        plan = plan_safe_ecom_repair(value)
        self.assertIn({
            "type": "addConnection",
            "source": "Shopify Build Brief",
            "target": "Message a model1",
        }, plan["operations"])

    def test_unknown_safety_issue_remains_blocker(self):
        value = workflow({
            "When clicking ‘Execute workflow’": {"main": [[{"node": "Shopify Build Brief"}, {"node": "Mystery"}]]},
            "Shopify Build Brief": {"main": [[{"node": "Message a model1"}]]},
            "Message a model1": {"main": [[{"node": "Message a model"}]]},
        })
        value["nodes"].append({"name": "Mystery", "type": "n8n-nodes-base.code", "disabled": False})
        plan = plan_safe_ecom_repair(value)
        self.assertFalse(plan["ok"])
        self.assertIn("unexpected_reachable_node:Mystery", plan["remaining_issues"])

    def test_legacy_removal_does_not_hide_other_reachable_unknown_node(self):
        value = workflow({
            "When clicking ‘Execute workflow’": {"main": [[{"node": "Shopify Build Brief"}, {"node": "Mystery"}]]},
            "Shopify Build Brief": {"main": [[{"node": "Message a model1"}]]},
            "Message a model1": {"main": [[{"node": "Message a model"}]]},
            "Message a model": {"main": [[{"node": "Edit a file"}]]},
        })
        value["nodes"].append({"name": "Mystery", "type": "n8n-nodes-base.code", "disabled": False})
        plan = plan_safe_ecom_repair(value)
        self.assertFalse(plan["ok"])
        self.assertIn("unexpected_reachable_node:Mystery", plan["remaining_issues"])
        self.assertNotIn("unexpected_reachable_node:Edit a file", plan["remaining_issues"])

    def test_malformed_body_fails_closed(self):
        plan = plan_safe_ecom_repair({"nodes": []})
        self.assertFalse(plan["ok"])
        self.assertEqual(plan["operations"], [])
        self.assertEqual(plan["remaining_issues"], ["malformed_workflow_body"])


if __name__ == "__main__":
    unittest.main()
