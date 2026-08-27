import unittest

import atlas_n8n


class N8NUnknownSchemaTypeTests(unittest.TestCase):
    def test_unknown_schema_type_fails_closed(self):
        schema = {
            "type": "object",
            "properties": {
                "workflowId": {"type": "mystery"},
            },
        }

        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "workflowId must be mystery"):
            atlas_n8n._validate_arguments_against_schema({"workflowId": "1"}, schema)

    def test_union_with_known_and_unknown_type_accepts_only_known_match(self):
        schema = {
            "type": "object",
            "properties": {
                "cursor": {"type": ["string", "mystery"]},
            },
        }

        atlas_n8n._validate_arguments_against_schema({"cursor": "next"}, schema)
        with self.assertRaisesRegex(atlas_n8n.N8NBridgeError, "cursor must be string or mystery"):
            atlas_n8n._validate_arguments_against_schema({"cursor": 5}, schema)


if __name__ == "__main__":
    unittest.main()
