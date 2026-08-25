import asyncio
import unittest

from atlas_autonomy import AutonomousTaskEngine


class AutonomyTests(unittest.IsolatedAsyncioTestCase):
    async def test_parallel_dependencies_and_retry(self):
        engine = AutonomousTaskEngine(concurrency=3)
        attempts = {"flaky": 0}

        async def ok(payload):
            await asyncio.sleep(.01)
            return payload["value"]

        async def flaky(payload):
            attempts["flaky"] += 1
            if attempts["flaky"] == 1:
                raise RuntimeError("temporary")
            return "recovered"

        engine.register_worker("ok", ok)
        engine.register_worker("flaky", flaky)
        task = engine.submit("build", [
            {"id": "a", "worker": "ok", "payload": {"value": "A"}},
            {"id": "b", "worker": "flaky"},
            {"id": "verify", "worker": "ok", "payload": {"value": "verified"}, "depends_on": ["a", "b"]},
        ])
        await engine._running[task.id]
        snap = engine.snapshot(task.id)
        self.assertEqual(snap["status"], "done")
        self.assertEqual(attempts["flaky"], 2)
        self.assertEqual(snap["steps"][2]["result"], "verified")

    async def test_blocked_step_does_not_prevent_independent_work(self):
        engine = AutonomousTaskEngine(concurrency=2)

        async def blocked(_):
            return {"status": "blocked", "reason": "2fa_required"}

        async def ok(_):
            return "done"

        engine.register_worker("blocked", blocked)
        engine.register_worker("ok", ok)
        task = engine.submit("goal", [
            {"id": "login", "worker": "blocked"},
            {"id": "docs", "worker": "ok"},
            {"id": "after-login", "worker": "ok", "depends_on": ["login"]},
        ])
        await engine._running[task.id]
        snap = engine.snapshot(task.id)
        states = {s["id"]: s["status"] for s in snap["steps"]}
        self.assertEqual(states["login"], "blocked")
        self.assertEqual(states["docs"], "done")
        self.assertEqual(states["after-login"], "blocked")
        self.assertEqual(snap["status"], "blocked")


if __name__ == "__main__":
    unittest.main()
