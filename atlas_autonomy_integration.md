# Atlas Autonomy Lifecycle Integration

Checkpoint branch: `atlas/autonomy-lifecycle`.

The runtime must be started inside the FastAPI lifespan event loop. The guarded patch script performs five exact, fail-closed edits to `main.py`: imports runtime helpers, constructs the runtime without starting tasks, starts it inside `api_lifespan`, stops it before closing the store, and exposes runtime health under `/health`.

CI applies the patch only in its temporary workspace first. If any expected anchor has changed or occurs more than once, the patch aborts instead of modifying production code. The contract test then confirms all lifecycle hooks and health wiring are present.

Do not merge lifecycle wiring into `main` until this branch's integration workflow is green.