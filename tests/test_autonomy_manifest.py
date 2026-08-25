import json
import unittest
from pathlib import Path


class ManifestTests(unittest.TestCase):
    def test_manifest_references_existing_components(self):
        data = json.loads(Path("AUTONOMY_MANIFEST.json").read_text(encoding="utf-8"))
        for path in data["runtime"] + data["integration"] + data["gates"] + [data["canary"]]:
            self.assertTrue(Path(path).exists(), path)


if __name__ == "__main__":
    unittest.main()
