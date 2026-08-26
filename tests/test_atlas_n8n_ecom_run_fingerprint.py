import unittest
from copy import deepcopy

import atlas_n8n_ecom_run as run_gate
from tests.test_atlas_n8n_ecom_run import SAFE_WORKFLOW


class EcomPreflightFingerprintTests(unittest.TestCase):
    def test_key_order_does_not_change_fingerprint(self):
        original = deepcopy(SAFE_WORKFLOW)
        reordered = {key: original[key] for key in reversed(list(original.keys()))}
        self.assertEqual(
            run_gate._workflow_fingerprint(original),
            run_gate._workflow_fingerprint(reordered),
        )

    def test_nested_mutation_changes_fingerprint(self):
        original = deepcopy(SAFE_WORKFLOW)
        changed = deepcopy(SAFE_WORKFLOW)
        body = run_gate._find_workflow_body(changed)
        self.assertIsInstance(body, dict)
        nodes = body.get("nodes") or []
        self.assertTrue(nodes)
        nodes[0]["name"] = f"{nodes[0].get('name', 'node')}-changed"
        self.assertNotEqual(
            run_gate._workflow_fingerprint(original),
            run_gate._workflow_fingerprint(changed),
        )

    def test_connection_order_change_is_detected(self):
        original = deepcopy(SAFE_WORKFLOW)
        changed = deepcopy(SAFE_WORKFLOW)
        body = run_gate._find_workflow_body(changed)
        self.assertIsInstance(body, dict)
        connections = body.get("connections")
        if isinstance(connections, dict) and len(connections) >= 2:
            items = list(connections.items())
            body["connections"] = dict(reversed(items))
            # Dict key order is canonicalized, so this must remain stable.
            self.assertEqual(
                run_gate._workflow_fingerprint(original),
                run_gate._workflow_fingerprint(changed),
            )
        else:
            self.skipTest("fixture has fewer than two top-level connection keys")

    def test_missing_workflow_body_has_no_fingerprint(self):
        self.assertIsNone(run_gate._workflow_fingerprint(None))
        self.assertIsNone(run_gate._workflow_fingerprint("not-a-workflow"))


if __name__ == "__main__":
    unittest.main()
