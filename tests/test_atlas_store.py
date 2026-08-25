import tempfile
import unittest
from pathlib import Path

from atlas_store import AtlasStore, AtlasStoreError, BudgetExceeded, TooManyJobs


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

    def test_files_are_durable_deduplicated_and_project_scoped(self):
        first = self.store.save_file(
            "project-atlas",
            name="brief.pdf",
            media_type="application/pdf",
            data="cGRmLWRhdGE=",
        )
        duplicate = self.store.save_file(
            "project-atlas",
            name="renamed.pdf",
            media_type="application/pdf",
            data="cGRmLWRhdGE=",
        )
        other = self.store.save_file(
            "project-shopify",
            name="brief.pdf",
            media_type="application/pdf",
            data="cGRmLWRhdGE=",
        )
        self.assertEqual(first["id"], duplicate["id"])
        self.assertNotEqual(first["id"], other["id"])
        self.assertEqual(len(self.store.list_files("project-atlas")), 1)
        self.assertIsNone(self.store.get_file("project-shopify", first["id"]))

        reopened = AtlasStore(sqlite_path=self.db_path)
        reopened.initialize()
        loaded = reopened.get_file("project-atlas", first["id"])
        self.assertEqual(loaded["data"], "cGRmLWRhdGE=")
        reopened.close()

        self.assertFalse(self.store.delete_file("project-shopify", first["id"]))
        self.assertTrue(self.store.delete_file("project-atlas", first["id"]))
        self.assertEqual(self.store.list_files("project-atlas"), [])


    def test_memory_normalization_prevents_cosmetic_duplicates(self):
        first = self.store.remember(
            "project-atlas",
            "Use PostgreSQL for durable jobs.",
            "decision",
        )
        duplicate = self.store.remember(
            "project-atlas",
            "  use postgresql for durable jobs!  ",
            "decision",
        )
        self.assertEqual(first["id"], duplicate["id"])
        self.assertEqual(
            len(self.store.search_memories("project-atlas", "")),
            1,
        )

    def test_memory_search_ranks_relevance_and_importance(self):
        self.store.remember(
            "project-shopify",
            "The storefront accent color is blue",
            "note",
        )
        important = self.store.remember(
            "project-shopify",
            "Use PostgreSQL for durable Shopify background jobs",
            "decision",
        )
        results = self.store.search_memories(
            "project-shopify",
            "durable postgres jobs",
            5,
        )
        self.assertEqual(results[0]["id"], important["id"])
        self.assertEqual(len(results), 1)
        self.assertGreater(results[0]["relevance_score"], 0)

    def test_project_context_includes_global_memory(self):
        self.store.remember(
            "project-general",
            "Always answer the user in Russian",
            "preference",
        )
        self.store.remember(
            "project-atlas",
            "Atlas uses Railway production",
            "fact",
        )
        context = self.store.memory_context("project-atlas", "Railway")
        self.assertIn("[project:fact] Atlas uses Railway production", context)
        self.assertIn("[global:preference] Always answer the user in Russian", context)

    def test_memory_can_be_edited_only_in_its_project(self):
        memory = self.store.remember(
            "project-atlas",
            "Old deployment rule",
            "decision",
        )
        self.assertIsNone(
            self.store.update_memory(
                "project-shopify",
                memory["id"],
                "New deployment rule",
                "decision",
            )
        )
        updated = self.store.update_memory(
            "project-atlas",
            memory["id"],
            "New deployment rule",
            "decision",
        )
        self.assertEqual(updated["id"], memory["id"])
        self.assertEqual(updated["content"], "New deployment rule")
        self.assertEqual(
            self.store.search_memories("project-atlas", "Old"),
            [],
        )

    def test_memory_health_reports_scope_without_deleting(self):
        self.store.remember("project-general", "Use Russian", "preference")
        self.store.remember("project-atlas", "Keep GREEN checkpoints", "decision")
        health = self.store.memory_health("project-atlas")
        self.assertEqual(health["total"], 1)
        self.assertEqual(health["global_total"], 1)
        self.assertEqual(health["by_kind"]["decision"], 1)
        self.assertFalse(health["automatic_deletion"])
        self.assertEqual(health["retrieval"], "ranked-local-and-global")


    def test_approval_request_is_durable_and_deduplicated(self):
        arguments = {
            "path": "README.md",
            "old_text": "old",
            "new_text": "new",
            "commit_message": "Update readme",
        }
        first = self.store.request_approval(
            tool="github_replace_text",
            arguments=arguments,
            summary="Change README",
            job_id="job-approval",
            project_id="project-atlas",
        )
        duplicate = self.store.request_approval(
            tool="github_replace_text",
            arguments=arguments,
            summary="Change README again",
            job_id="job-approval",
            project_id="project-atlas",
        )
        self.assertEqual(first["id"], duplicate["id"])
        self.assertEqual(first["status"], "pending")

        reopened = AtlasStore(sqlite_path=self.db_path)
        reopened.initialize()
        approvals = reopened.list_approvals("project-atlas")
        self.assertEqual(len(approvals), 1)
        self.assertEqual(approvals[0]["arguments"]["path"], "README.md")
        reopened.close()

    def test_approval_is_claimed_and_completed_once(self):
        approval = self.store.request_approval(
            tool="github_write_file",
            arguments={
                "path": "notes.txt",
                "content": "safe content",
                "commit_message": "Add notes",
            },
            summary="Create notes",
            project_id="project-atlas",
        )
        self.assertIsNone(
            self.store.claim_approval(
                "project-shopify",
                approval["id"],
                "worker-wrong",
            )
        )
        claimed = self.store.claim_approval(
            "project-atlas",
            approval["id"],
            "worker-one",
        )
        self.assertEqual(claimed["status"], "executing")
        self.assertIsNone(
            self.store.claim_approval(
                "project-atlas",
                approval["id"],
                "worker-two",
            )
        )
        self.assertFalse(
            self.store.complete_approval(
                "project-atlas",
                approval["id"],
                "worker-two",
                {"ok": True},
            )
        )
        self.assertTrue(
            self.store.complete_approval(
                "project-atlas",
                approval["id"],
                "worker-one",
                {"ok": True, "commit_sha": "abc123"},
            )
        )
        completed = self.store.get_approval("project-atlas", approval["id"])
        self.assertEqual(completed["status"], "approved")
        self.assertEqual(completed["result"]["commit_sha"], "abc123")
        self.assertFalse(
            self.store.reject_approval("project-atlas", approval["id"])
        )

    def test_pending_approval_can_be_rejected_only_in_its_project(self):
        approval = self.store.request_approval(
            tool="github_write_file",
            arguments={
                "path": "draft.txt",
                "content": "draft",
                "commit_message": "Draft",
            },
            summary="Create draft",
            project_id="project-promo",
        )
        self.assertFalse(
            self.store.reject_approval("project-atlas", approval["id"])
        )
        self.assertTrue(
            self.store.reject_approval("project-promo", approval["id"])
        )
        rejected = self.store.get_approval("project-promo", approval["id"])
        self.assertEqual(rejected["status"], "rejected")

    def test_approval_payload_size_is_bounded(self):
        with self.assertRaises(AtlasStoreError):
            self.store.request_approval(
                tool="github_write_file",
                arguments={
                    "path": "huge.txt",
                    "content": "x" * 500_001,
                    "commit_message": "Huge",
                },
                summary="Oversized write",
                project_id="project-atlas",
            )


if __name__ == "__main__":
    unittest.main()
