import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from atlas_push import PushService, generate_vapid_config
from atlas_store import AtlasStore


def decode_urlsafe(value):
    value += "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value.encode("ascii"))


class AtlasPushTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = AtlasStore(
            database_url="",
            sqlite_path=str(Path(self.tempdir.name) / "atlas.db"),
        )
        self.store.initialize()
        self.push = PushService(self.store)

    def tearDown(self):
        self.store.close()
        self.tempdir.cleanup()

    def test_vapid_config_is_valid_and_durable(self):
        generated = generate_vapid_config()
        public = decode_urlsafe(generated["public_key"])
        private = decode_urlsafe(generated["private_key"])
        self.assertEqual(len(public), 65)
        self.assertEqual(public[0], 4)
        self.assertGreater(len(private), 100)

        first = self.push.ensure_config()
        second_service = PushService(self.store)
        second = second_service.ensure_config()
        self.assertEqual(first, second)
        self.assertNotIn(first["private_key"], json.dumps(self.push.public_status()))

    def test_subscription_is_upserted_and_can_be_removed(self):
        payload = {
            "endpoint": "https://push.example.test/device-1",
            "keys": {"p256dh": "public-device-key", "auth": "auth-secret"},
        }
        first = self.push.subscribe(payload, "Atlas test")
        second = self.push.subscribe(payload, "Atlas test updated")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.store.push_subscription_count(), 1)
        self.assertTrue(self.push.unsubscribe(payload["endpoint"]))
        self.assertEqual(self.store.push_subscription_count(), 0)

    @patch("atlas_push.webpush")
    def test_completion_is_sent_without_exposing_job_content(self, mocked_webpush):
        self.push.subscribe(
            {
                "endpoint": "https://push.example.test/device-2",
                "keys": {"p256dh": "device-key", "auth": "device-auth"},
            }
        )
        result = self.push.send_completion(
            job_id="job-123",
            project_id="project-atlas",
        )
        self.assertEqual(result["sent"], 1)
        payload = json.loads(mocked_webpush.call_args.kwargs["data"])
        self.assertEqual(payload["tag"], "atlas-job-job-123")
        self.assertEqual(payload["body"], "Задача выполнена")
        self.assertNotIn("private_key", payload)


if __name__ == "__main__":
    unittest.main()
