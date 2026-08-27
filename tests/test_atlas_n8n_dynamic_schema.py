import unittest

import atlas_n8n


class N8NDynamicSchemaTests(unittest.TestCase):
    def test_additional_properties_schema_validates_dynamic_values(self):
        schema = {
            "type": "object",
            "properties": {
                "labels": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": {"type": "string", "maxLength": 8},
                }
            },
        }
        atlas_n8n._validate_arguments_against_schema({"labels": {"team": "atlas"}}, schema)
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "exceeds maxLength"):
            atlas_n8n._validate_arguments_against_schema(
                {"labels": {"team": "atlas-core"}}, schema
            )

    def test_additional_properties_schema_rejects_wrong_dynamic_type(self):
        schema = {
            "type": "object",
            "properties": {
                "metadata": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": {"type": "integer", "minimum": 0},
                }
            },
        }
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "metadata.retry must be integer"):
            atlas_n8n._validate_arguments_against_schema(
                {"metadata": {"retry": "three"}}, schema
            )
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "below minimum"):
            atlas_n8n._validate_arguments_against_schema(
                {"metadata": {"retry": -1}}, schema
            )

    def test_dynamic_object_values_are_validated_recursively(self):
        schema = {
            "type": "object",
            "properties": {
                "nodes": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": {
                        "type": "object",
                        "required": ["enabled"],
                        "properties": {"enabled": {"type": "boolean"}},
                        "additionalProperties": False,
                    },
                }
            },
        }
        atlas_n8n._validate_arguments_against_schema(
            {"nodes": {"shopify": {"enabled": True}}}, schema
        )
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "missing required field.*nodes.shopify"):
            atlas_n8n._validate_arguments_against_schema(
                {"nodes": {"shopify": {}}}, schema
            )
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "undeclared field.*nodes.shopify"):
            atlas_n8n._validate_arguments_against_schema(
                {"nodes": {"shopify": {"enabled": True, "token": "blocked"}}}, schema
            )


if __name__ == "__main__":
    unittest.main()
