# Handoff

Current branch contains the autonomous execution engine and a guarded production integration path. If another model or engineer continues the work, do not rebuild the engine from scratch. Start with `AUTONOMY_CHECKPOINT.json`, `AUTONOMY_ACCEPTANCE.md`, and `AUTONOMY_ROLLOUT.md`; then inspect `atlas_autonomy.py`, `atlas_autonomy_store.py`, `atlas_autonomy_workers.py`, and `atlas_autonomy_runtime.py`.

Immediate next operation is PR validation. Only after green CI should `scripts/patch_main_autonomy.py` be applied to branch `main.py`, retested, merged, deployed, and exercised with `AUTONOMY_CANARY.json`.