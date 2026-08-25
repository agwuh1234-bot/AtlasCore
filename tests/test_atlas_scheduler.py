import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlas_scheduler import normalize_schedule, next_run_at
from atlas_store import AtlasStore


class SchedulerCalculationTests(unittest.TestCase):
    def test_daily_schedule_uses_kyiv_local_time(self):
        config = normalize_schedule(
            frequency="daily",
            timezone_name="Europe/Kyiv",
            time_local="09:00",
        )
        # On 2026-01-15 Kyiv is UTC+2, so 09:00 local is 07:00 UTC.
        after = datetime(2026, 1, 15, 6, 0, tzinfo=timezone.utc).timestamp()
        result = datetime.fromtimestamp(next_run_at(config, after), timezone.utc)
        self.assertEqual((result.hour, result.minute), (7, 0))

    def test_weekly_schedule_uses_selected_days(self):
        config = normalize_schedule(
            frequency="weekly",
            timezone_name="Europe/Berlin",
            time_local="12:30",
            weekdays=[2],
        )
        after = datetime(2026, 1, 19, 15, 0, tzinfo=timezone.utc).timestamp()
        result = datetime.fromtimestamp(next_run_at(config, after), timezone.utc)
        self.assertEqual(result.date().isoformat(), "2026-01-21")
        self.assertEqual((result.hour, result.minute), (11, 30))

    def test_once_schedule_does_not_repeat(self):
        config = normalize_schedule(
            frequency="once",
            timezone_name="Europe/Berlin",
            run_at="2026-02-01T10:00",
        )
        before = datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc).timestamp()
        after = datetime(2026, 2, 1, 10, 0, tzinfo=timezone.utc).timestamp()
        self.assertIsNotNone(next_run_at(config, before))
        self.assertIsNone(next_run_at(config, after))


class DurableSchedulerStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.store = AtlasStore(database_url="", sqlite_path=str(Path(self.tempdir.name) / "atlas.db"))
        self.store.initialize()

    def tearDown(self):
        self.store.close()
        self.tempdir.cleanup()

    def test_recurring_schedule_is_claimed_once_and_moves_forward(self):
        schedule = self.store.create_schedule("project-atlas", name="Daily check", task="Check project status", frequency="daily", timezone_name="Europe/Berlin", time_local="09:00")
        due = float(schedule["next_run_at"]) + 1
        claimed = self.store.claim_due_schedules(due, "worker-a", 3)
        self.assertEqual([item["id"] for item in claimed], [schedule["id"]])
        self.assertEqual(self.store.claim_due_schedules(due, "worker-b", 3), [])
        self.assertTrue(self.store.finish_schedule_claim(schedule["id"], "worker-a", "job-1"))
        updated = self.store.get_schedule("project-atlas", schedule["id"])
        self.assertTrue(updated["enabled"])
        self.assertGreater(updated["next_run_at"], due)
        self.assertEqual(updated["last_job_id"], "job-1")

    def test_once_schedule_disables_after_claim_and_is_project_scoped(self):
        schedule = self.store.create_schedule("project-shopify", name="Launch check", task="Prepare launch checklist", frequency="once", timezone_name="Europe/Berlin", run_at="2099-01-01T12:00")
        self.assertIsNone(self.store.get_schedule("project-atlas", schedule["id"]))
        claimed = self.store.claim_due_schedules(float(schedule["next_run_at"]) + 1, "worker", 3)
        self.assertEqual(len(claimed), 1)
        updated = self.store.get_schedule("project-shopify", schedule["id"])
        self.assertFalse(updated["enabled"])
        self.assertIsNone(updated["next_run_at"])

    def test_schedule_delete_is_project_scoped(self):
        schedule = self.store.create_schedule("project-promo", name="Promo report", task="Summarize promo status", frequency="weekly", timezone_name="Europe/Berlin", time_local="18:00", weekdays=[0])
        self.assertFalse(self.store.delete_schedule("project-atlas", schedule["id"]))
        self.assertTrue(self.store.delete_schedule("project-promo", schedule["id"]))


if __name__ == "__main__":
    unittest.main()
