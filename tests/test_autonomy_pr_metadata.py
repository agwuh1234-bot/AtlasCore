import json
import unittest
from pathlib import Path


class PRMetadataTests(unittest.TestCase):
    def test_metadata_targets_main(self):
        data = json.loads(Path("AUTONOMY_PR_METADATA.json").read_text())
        self.assertEqual(data["head"], "atlas/autonomy-lifecycle")
        self.assertEqual(data["base"], "main")


if __name__ == "__main__":
    unittest.main()
