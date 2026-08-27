import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "patch_main_autonomy.py"


class PatchTests(unittest.TestCase):
    def test_patch_refuses_unknown_main(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "main.py").write_text("print('different')\n", encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT)], cwd=td, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Refusing patch", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
