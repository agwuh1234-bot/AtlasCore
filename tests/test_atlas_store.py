import tempfile
import unittest
from pathlib import Path

from atlas_store import AtlasStore, BudgetExceeded, TooManyJobs


class AtlasStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tempdir.name) / "atlas.db")
        self.store = AtlasStore(sqlite_path=self.db_path)
        self.store.initialize()

    def tearDown(self):
        self.store.close()
        self.tempdir.cleanup()

    def test_default_projects_have_stable_order(self):
        projects = self.store.list_projects()
        self.assertEqual(
            [item["id"] for item in projects[:4]],
            [
                "project-general",
                "project-atlas",
                "project-shopify",
                "project-promo",
            ],
        )

    def test_same_memory_can_exist_in_two_projects(self):
        first = self.store.remember("project-atlas", "Use a durable queue", "decision")
        second = self.store.remember("project-shopify", "Use a durable queue", "decision")
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.search_memories("project-atlas", "durable")), 1)
        self.assertEqual(len(self.store.search_memories("project-shopify", "durable")), 1)

    def test_memory_can_be_deleted_only_from_its_project(self):
        memory = self.store.remember("project-atlas", "Keep this", "decision")
        self.assertFalse(self.store.delete_memory("project-shopify", memory["id"]))
        self.assertTrue(self.store.delete_memory("project-atlas", memory["id"]))
        self.assertEqual(self.store.search_memories("project-atlas", "Keep"), [])

    def test_job_survives_store_reopen(self):
        created = self.store.create_job(
            {
                "task": "ping",
                "project_id": "project-atlas",
                "allow_writes": False,
                "attachments": [],
            }
        )
        reopened = AtlasStore(sqlite_path=self.db_path)
        reopened.initialize()
        loaded = reopened.get_job(created["job_id"])
        self.assertEqual(loaded["status"], "queued")
        self.assertEqual(loaded["payload"]["task"], "ping")
        reopened.close()

    def test_safe_stale_job_requeues_once(self):
        created = self.store.create_job(
            {
                "task": "read only",
                "project_id": "project-atlas",
                "allow_writes": False,
                "attachments": [],
            }
        )
        claimed = self.store.claim_next_job("worker-old")
        self.assertEqual(claimed["job_id"], created["job_id"])
        outcome = self.store.recover_stale_jobs(stale_after=0)
        recovered = self.store.get_job(created["job_id"])
        self.assertEqual(outcome["recovered"], 1)
        self.assertEqual(recovered["status"], "queued")
        self.assertEqual(recovered["retry_count"], 1)
        self.store.claim_next_job("worker-new")
        self.store.recover_stale_jobs(stale_after=0)
        self.assertEqual(self.store.get_job(created["job_id"])["status"], "error")

    def test_write_job_never_requeues_after_interruption(self):
        created = self.store.create_job(
            {
                "task": "change code",
                "project_id": "project-atlas",
                "allow_writes": True,
                "attachments": [],
            }
        )
        self.store.claim_next_job("worker-old")
        outcome = self.store.recover_stale_jobs(stale_after=0)
        self.assertEqual(outcome["failed"], 1)
        self.assertEqual(self.store.get_job(created["job_id"])["status"], "error")

    def test_cancelled_job_cannot_be_overwritten(self):
        created = self.store.create_job(
            {
                "task": "wait",
                "project_id": "project-general",
                "allow_writes": False,
                "attachments": [],
            }
        )
        self.store.claim_next_job("worker")
        self.store.cancel_job(created["job_id"])
        written = self.store.finish_job(created["job_id"], "late result", "resp")
        self.assertFalse(written)
        self.assertEqual(self.store.get_job(created["job_id"])["status"], "cancelled")

    def test_active_job_limit_is_atomic(self):
        limited = AtlasStore(
            sqlite_path=str(Path(self.tempdir.name) / "limited.db"),
            max_active_jobs=1,
        )
        limited.initialize()
        limited.create_job({"task": "one", "attachments": [], "allow_writes": False})
        with self.assertRaises(TooManyJobs):
            limited.create_job({"task": "two", "attachments": [], "allow_writes": False})
        limited.close()

    def test_budget_reservation_and_usage(self):
        first = self.store.reserve_budget(
            "job-1",
            "gpt-test",
            0.30,
            daily_limit_usd=0.50,
            task_limit_usd=0.40,
        )
        with self.assertRaises(BudgetExceeded):
            self.store.reserve_budget(
                "job-2",
                "gpt-test",
                0.30,
                daily_limit_usd=0.50,
                task_limit_usd=0.40,
            )
        self.store.complete_budget(
            first["id"],
            job_id="job-1",
            project_id="project-atlas",
            model="gpt-test",
            input_tokens=100,
            output_tokens=50,
            web_calls=0,
            cost_usd=0.10,
        )
        status = self.store.budget_status(0.50)
        self.assertAlmostEqual(status["spent_usd"], 0.10)
        self.assertAlmostEqual(status["reserved_usd"], 0.0)


if __name__ == "__main__":
    unittest.main()
