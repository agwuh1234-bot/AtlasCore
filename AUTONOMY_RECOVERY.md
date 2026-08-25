# Restart recovery semantics

Every graph transition is checkpointed. On runtime start, active durable graphs are loaded. Steps left in `running` or `retrying` by process death are returned to `queued` and restarted from the worker boundary. Completed steps stay completed.

Because a crash can happen after an external side effect but before its checkpoint, write-capable workers must verify current external state or use idempotency before repeating a write. Browser canary testing is read-only until this property is demonstrated for each write-capable integration.