# Autonomous Task Engine rollout gate

1. Autonomous unit tests must pass.
2. Guarded lifecycle patch must apply to the current `main.py` exactly once per anchor.
3. Patched `main.py` and autonomy modules must compile.
4. Lifecycle contract must pass.
5. Merge only after CI is green.
6. Verify Railway deployment and `/health.autonomy.started == true`.
7. Submit a harmless public browser graph and verify completion/checkpointing.
8. Restart/redeploy and verify unfinished graph recovery.
9. Only then enable persistent authenticated Shopify sessions.

Rollback: revert the lifecycle integration commit; autonomous checkpoint rows remain inert and can be resumed after a fixed deployment.