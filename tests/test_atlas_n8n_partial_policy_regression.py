import unittest

import atlas_n8n


class N8NPartialWorkflowPolicyRegressionTests(unittest.TestCase):
    def test_unknown_partial_operation_fails_closed(self):
        arguments = {
            "workflowId": "wf-1",
            "operations": [{"type": "futureVendorMutation", "nodeName": "Critical"}],
        }
        self.assertTrue(atlas_n8n._contains_destructive_workflow_operation(arguments))

    def test_empty_operation_type_fails_closed(self):
        arguments = {
            "workflowId": "wf-1",
            "operations": [{"type": "", "nodeName": "Critical"}],
        }
        self.assertTrue(atlas_n8n._contains_destructive_workflow_operation(arguments))

    def test_known_add_and_update_operations_remain_non_destructive(self):
        arguments = {
            "workflowId": "wf-1",
            "operations": [
                {"type": "addNode", "node": {"name": "New Node"}},
                {"type": "updateNode", "nodeName": "New Node"},
                {"type": "updateNodeParameters", "nodeName": "New Node"},
                {"type": "addConnection", "source": "A", "target": "B"},
            ],
        }
        self.assertFalse(atlas_n8n._contains_destructive_workflow_operation(arguments))

    def test_set_node_disabled_requires_explicit_boolean(self):
        ambiguous = {
            "workflowId": "wf-1",
            "operations": [{"type": "setNodeDisabled", "nodeName": "Critical", "disabled": "false"}],
        }
        enabled = {
            "workflowId": "wf-1",
            "operations": [{"type": "setNodeDisabled", "nodeName": "Critical", "disabled": False}],
        }
        self.assertTrue(atlas_n8n._contains_destructive_workflow_operation(ambiguous))
        self.assertFalse(atlas_n8n._contains_destructive_workflow_operation(enabled))


if __name__ == "__main__":
    unittest.main()
