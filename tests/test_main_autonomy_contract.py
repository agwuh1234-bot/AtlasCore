import unittest
from pathlib import Path


class MainAutonomyContractTests(unittest.TestCase):
    def test_main_wires_autonomy_runtime_into_fastapi_lifespan(self):
        source = Path("main.py").read_text(encoding="utf-8")
        self.assertIn("from atlas_autonomy_runtime import", source)
        self.assertIn("build_autonomy_runtime", source)
        self.assertIn("start_autonomy_runtime", source)
        self.assertIn("stop_autonomy_runtime", source)
        self.assertIn("AUTONOMY_RUNTIME", source)
        self.assertIn("await start_autonomy_runtime(AUTONOMY_RUNTIME)", source)
        self.assertIn("await stop_autonomy_runtime(AUTONOMY_RUNTIME)", source)

    def test_health_exposes_autonomy(self):
        source = Path("main.py").read_text(encoding="utf-8")
        self.assertIn('"autonomy": AUTONOMY_RUNTIME.health()', source)


if __name__ == "__main__":
    unittest.main()
