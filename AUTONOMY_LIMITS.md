# Execution limits

Default graph concurrency is 5 and configuration is clamped to 1..10. Individual step retries default to 3 and are clamped to at most 10. Browser worker timeout is clamped to 5..300 seconds. These bounds prevent a malformed plan from creating unbounded parallelism, retry storms, or permanently occupied browser workers.

Limits can be tuned after production telemetry exists; they should not be removed merely to make autonomy appear unlimited.