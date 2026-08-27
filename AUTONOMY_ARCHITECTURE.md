# Atlas Autonomous Execution

Goal -> dependency graph -> concurrent workers -> verification -> retry/checkpoint -> next step.

Durability: `AtlasAutonomyStore` persists graph snapshots in PostgreSQL. Runtime recovery converts interrupted `running`/`retrying` steps back to queued boundaries and resumes the graph.

Workers: browser performs BrowserJobManager jobs, verify performs deterministic assertions, approval blocks only the branch requiring user action. More workers can be registered without changing the engine.

Safety: concurrency is bounded; retries are bounded; lifecycle startup occurs inside FastAPI's asyncio loop; browser auth state is encrypted; production rollout is gated by CI and health/recovery checks.

The long-term target is that ChatGPT can delegate a goal once and Atlas keeps executing it independently of individual chat turns.