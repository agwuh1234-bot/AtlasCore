from pathlib import Path
import unittest


class ServiceWorkerPushPayloadBoundsTests(unittest.TestCase):
    def test_push_text_is_bounded_before_show_notification(self):
        source = Path("web/sw.js").read_text(encoding="utf-8")
        self.assertIn("function boundedNotificationText", source)
        self.assertIn("boundedNotificationText(payload.title", source)
        self.assertIn("boundedNotificationText(payload.body", source)
        self.assertIn("boundedNotificationText(payload.tag", source)
        self.assertNotIn("body: payload.body || 'Задача выполнена'", source)
        self.assertNotIn("tag: payload.tag || 'atlas-done'", source)


if __name__ == "__main__":
    unittest.main()
