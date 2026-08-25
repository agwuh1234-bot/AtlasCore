# Rollback

If the production autonomy runtime causes startup, health, browser-worker, or recovery failures:

1. Revert only the lifecycle wiring commit from `main`.
2. Redeploy the previously healthy application revision.
3. Leave `atlas_autonomous_tasks` rows untouched.
4. Diagnose/fix on a branch and rerun CI.
5. Redeploy the corrected runtime; `resume_all()` can then recover active durable graphs.

Do not delete encrypted browser sessions or PostgreSQL checkpoints as part of a routine code rollback.