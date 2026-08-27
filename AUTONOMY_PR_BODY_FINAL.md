Adds Atlas's durable autonomous execution foundation: dependency-aware concurrent task graphs, bounded retries, PostgreSQL checkpoints, restart recovery, Browser/Verify/Approval workers, encrypted browser-session integration, and a FastAPI-loop-safe runtime.

Production wiring is intentionally gated. CI first applies the fail-closed lifecycle patch in an ephemeral checkout and validates compilation/contracts. After that passes, the exact patch can be applied to the branch source and CI rerun before merge. Post-merge rollout requires Railway health, a harmless read-only browser canary, and controlled restart recovery before authenticated Shopify automation is enabled.

Rollback preserves durable graph checkpoints and encrypted browser sessions.