import unittest

import atlas_n8n


class N8NNestedSchemaTests(unittest.TestCase):
    def test_nested_required_field_is_enforced(self):
        schema = {
            "type": "object",
            "properties": {
                "payload": {
                    "type": "object",
                    "required": ["mode"],
                    "properties": {"mode": {"type": "string"}},
                    "additionalProperties": False,
                }
            },
        }
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "missing required field.*payload"):
            atlas_n8n._validate_arguments_against_schema({"payload": {}}, schema)

    def test_nested_unknown_field_is_blocked(self):
        schema = {
            "type": "object",
            "properties": {
                "payload": {
                    "type": "object",
                    "properties": {"mode": {"type": "string"}},
                    "additionalProperties": False,
                }
            },
        }
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "undeclared field.*payload"):
            atlas_n8n._validate_arguments_against_schema(
                {"payload": {"mode": "safe", "secretExtra": True}}, schema
            )

    def test_array_item_constraints_are_enforced(self):
        schema = {
            "type": "object",
            "properties": {
                "operations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["type"],
                        "properties": {
                            "type": {"type": "string", "enum": ["addNode"]},
                            "count": {"type": "integer", "minimum": 1},
                        },
                        "additionalProperties": False,
                    },
                }
            },
        }
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, r"operations\[0\]\.count is below minimum"):
            atlas_n8n._validate_arguments_against_schema(
                {"operations": [{"type": "addNode", "count": 0}]}, schema
            )

    def test_nested_valid_payload_passes(self):
        schema = {
            "type": "object",
            "properties": {
                "payload": {
                    "type": "object",
                    "required": ["mode"],
                    "properties": {
                        "mode": {"type": "string", "enum": ["safe"]},
                        "items": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "integer", "minimum": 1},
                        },
                    },
                    "additionalProperties": False,
                }
            },
        }
        atlas_n8n._validate_arguments_against_schema(
            {"payload": {"mode": "safe", "items": [1, 2]}}, schema
        )


if __name__ == "__main__":
    unittest.main()
