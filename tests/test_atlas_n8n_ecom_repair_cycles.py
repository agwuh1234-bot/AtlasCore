import unittest

from atlas_n8n_ecom_repair import (
    SHOPIFY_BRIEF_NODE,
    TRIGGER_NODE,
    _planned_reachable_cycle,
)


def connections(*edges):
    result = {}
    for source, target in edges:
        result.setdefault(source, {"main": [[]]})["main"][0].append({"node": target, "type": "main", "index": 0})
    return result


class EcomRepairCycleTests(unittest.TestCase):
    def test_linear_safe_path_has_no_cycle(self):
        body = {
            "connections": connections(
                (TRIGGER_NODE, SHOPIFY_BRIEF_NODE),
                (SHOPIFY_BRIEF_NODE, "Message a model1"),
                ("Message a model1", "Message a model"),
            )
        }
        self.assertFalse(_planned_reachable_cycle(body, []))

    def test_reachable_cycle_is_blocked(self):
        body = {
            "connections": connections(
                (TRIGGER_NODE, SHOPIFY_BRIEF_NODE),
                (SHOPIFY_BRIEF_NODE, "Message a model1"),
                ("Message a model1", "Message a model"),
                ("Message a model", SHOPIFY_BRIEF_NODE),
            )
        }
        self.assertTrue(_planned_reachable_cycle(body, []))

    def test_disconnected_cycle_does_not_block_manual_pipeline(self):
        body = {
            "connections": connections(
                (TRIGGER_NODE, SHOPIFY_BRIEF_NODE),
                (SHOPIFY_BRIEF_NODE, "Message a model1"),
                ("Message a model1", "Message a model"),
                ("Detached A", "Detached B"),
                ("Detached B", "Detached A"),
            )
        }
        self.assertFalse(_planned_reachable_cycle(body, []))

    def test_planned_addition_that_creates_cycle_is_blocked(self):
        body = {
            "connections": connections(
                (TRIGGER_NODE, SHOPIFY_BRIEF_NODE),
                (SHOPIFY_BRIEF_NODE, "Message a model1"),
                ("Message a model1", "Message a model"),
            )
        }
        operations = [
            {"type": "addConnection", "source": "Message a model", "target": SHOPIFY_BRIEF_NODE}
        ]
        self.assertTrue(_planned_reachable_cycle(body, operations))


if __name__ == "__main__":
    unittest.main()
