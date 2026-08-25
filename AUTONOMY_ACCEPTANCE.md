# Acceptance criteria

Atlas autonomy is production-ready only when all of these are demonstrated:

- multiple independent steps can execute concurrently;
- dependent steps wait for prerequisites;
- transient failures retry within a fixed bound;
- blocked approval branches do not stop unrelated work;
- graph state survives process restart in PostgreSQL;
- browser worker executes a real read-only Chromium job;
- `/health` reports autonomy runtime started;
- shutdown cancels in-process tasks cleanly without deleting checkpoints;
- an unfinished canary resumes after controlled Railway restart;
- authenticated Shopify automation remains disabled until the read-only canary and restart recovery both pass.
