import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CoreWriteGuardTests(unittest.TestCase):
    def test_guard_loads_before_core_runtime(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        guard = '/app/core-write-guard.js?v=20260827-write1'
        core = '/app/core.js?v=20260827-core1'
        self.assertIn(guard, html)
        self.assertIn(core, html)
        self.assertLess(html.index(guard), html.index(core))

    def test_enabling_writes_requires_second_click(self):
        js = (ROOT / "web" / "core-write-guard.js").read_text(encoding="utf-8")
        self.assertIn('var ARM_MS=5000', js)
        self.assertIn("event.preventDefault();", js)
        self.assertIn("event.stopImmediatePropagation();", js)
        self.assertIn("data-write-armed", js)
        self.assertIn("Date.now()<=armedUntil", js)
        self.assertIn("if(alreadyOn){clearArm();return}", js)

    def test_guard_expires_when_page_is_hidden_or_left(self):
        js = (ROOT / "web" / "core-write-guard.js").read_text(encoding="utf-8")
        self.assertIn("setTimeout(clearArm,ARM_MS)", js)
        self.assertIn("pagehide", js)
        self.assertIn("visibilitychange", js)
        self.assertIn("if(document.hidden)clearArm()", js)

    def test_core_still_passes_write_state_to_server(self):
        js = (ROOT / "web" / "core.js").read_text(encoding="utf-8")
        self.assertIn("allow_writes:state.writes", js)


if __name__ == "__main__":
    unittest.main()
