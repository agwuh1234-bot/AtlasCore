# Autonomy operations

Healthy production state: `/health` contains an `autonomy` object with `started: true`. `active_tasks` may be zero when idle. `resumed_tasks` reports how many durable graphs were restored at the current runtime start.

If autonomy startup fails, do not delete PostgreSQL checkpoints. Roll back lifecycle wiring, fix the runtime, redeploy, and let recovery resume active graphs.

For the first production canary use only a harmless public URL and read-only browser actions. Verify completion, persisted checkpoint state, then perform a controlled restart and verify recovery before enabling authenticated Shopify automation.