import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ThreadContextPersistenceTests(unittest.TestCase):
    def test_threads_snapshot_response_and_active_job_context(self):
        source = (ROOT / "web" / "sidebar.js").read_text(encoding="utf-8")
        self.assertIn("RID='atlas_response_id'", source)
        self.assertIn("JID='atlas_active_job_id'", source)
        self.assertIn("response_id:localStorage.getItem(RID)||''", source)
        self.assertIn("active_job_id:localStorage.getItem(JID)||''", source)

    def test_open_thread_restores_backend_continuation(self):
        source = (ROOT / "web" / "sidebar.js").read_text(encoding="utf-8")
        self.assertIn("setStored(RID,t.response_id||'')", source)
        self.assertIn("setStored(JID,t.active_job_id||'')", source)
        self.assertIn("location.reload()", source)

    def test_new_thread_detaches_without_cancelling_old_job(self):
        source = (ROOT / "web" / "sidebar.js").read_text(encoding="utf-8")
        self.assertIn("localStorage.setItem(H,'[]')", source)
        self.assertIn("setStored(RID,'')", source)
        self.assertIn("setStored(JID,'')", source)
        self.assertNotIn("method:'DELETE'", source)


if __name__ == "__main__":
    unittest.main()
