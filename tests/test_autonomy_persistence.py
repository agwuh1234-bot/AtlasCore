import asyncio
import unittest

from atlas_autonomy import AutonomousTaskEngine


class MemoryCheckpointStore:
    def __init__(self):
        self.items = {}
    def save(self, task):
        self.items[task["id"]] = task
    def load_active(self):
        return [v for v in self.items.values() if v["status"] in {"queued", "running"}]


class PersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_checkpoints_each_transition(self):
        store = MemoryCheckpointStore()
        engine = AutonomousTaskEngine(checkpoint_store=store)
        async def ok(payload): return payload.get("x", 1)
        engine.register_worker("ok", ok)
        task = engine.submit("goal", [{"id": "one", "worker": "ok", "payload": {"x": 7}}])
        await engine._running[task.id]
        self.assertEqual(store.items[task.id]["status"], "done")
        self.assertEqual(store.items[task.id]["steps"][0]["result"], 7)

    async def test_resume_running_checkpoint(self):
        store = MemoryCheckpointStore()
        store.items["task1"] = {
            "id": "task1", "goal": "resume", "status": "running",
            "created_at": 1, "updated_at": 2,
            "steps": [{"id": "a", "title": "a", "worker": "ok", "payload": {},
                       "depends_on": [], "status": "running", "attempts": 0, "max_attempts": 3,
                       "result": None, "error": None}],
        }
        engine = AutonomousTaskEngine(checkpoint_store=store)
        async def ok(_): return "resumed"
        engine.register_worker("ok", ok)
        self.assertEqual(engine.resume_all(), 1)
        await engine._running["task1"]
        self.assertEqual(engine.snapshot("task1")["status"], "done")
        self.assertEqual(engine.snapshot("task1")["steps"][0]["result"], "resumed")


if __name__ == "__main__":
    unittest.main()
