## Atlas Autonomous Task Engine

Adds durable dependency-graph execution with bounded concurrency/retries, PostgreSQL checkpoints and restart recovery, real browser/verification/approval worker adapters, encrypted browser-session support, and an event-loop-safe FastAPI runtime.

### Rollout safety
The branch does not directly overwrite production `main.py`. A fail-closed patch script requires exact unique anchors. CI first applies that patch in an ephemeral checkout, compiles the resulting source and validates lifecycle wiring. Production merge is gated on green CI, followed by a read-only Railway browser canary and controlled restart-recovery test before authenticated Shopify automation is enabled.

### Rollback
Revert lifecycle wiring. Durable graph checkpoints remain stored and can be resumed after a corrected deployment.