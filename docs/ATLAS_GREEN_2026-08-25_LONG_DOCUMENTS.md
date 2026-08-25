# AtlasCore GREEN checkpoint — Long Documents + Learned Skills

Date: 2026-08-25
Status: GREEN

## Verified production state

- Application commit: `6f8742f441499928ef8b7ca472b9e4c8a6744290`
- Core long-document implementation: `7ba0f146977542305f76abecb7515f33a1ef07b6`
- Long-document regression tests: `80556492946c93695cc62d15abeca967e101de8e`
- Learned-document skill policy: `f3252aa3c3314dc338b896a81c3e3af8bd8d2f14`
- Railway deployment: `544e3a77-2895-426a-b3a2-de31b193ab60` — SUCCESS
- Production tests: 41/41 passed
- Smoke check: `ATLAS_SMOKE_OK`
- Railway health check: `GET /health` returned HTTP 200

## Long-document fix included

- Ordinary chat remains protected by the normal 50,000-input-token budget guard.
- Real attached documents may automatically enter bounded long-document mode.
- Long-document hard ceiling is 950,000 counted input tokens by default.
- The failing 796,306-token PDF case is covered by a production regression test.
- Oversized plain-text/history requests cannot use the document exception.
- Documents beyond the hard ceiling are rejected with a clear split/analyze-in-parts message.
- File-only analysis routes to the dedicated `document` lane using GPT-5.6 Terra by default.
- Coding/complex attachment tasks continue to route to the strongest model.
- Long-context requests use a separate conservative cost reservation instead of multiplying the giant file by the normal multi-turn reserve.

## Learned document skills

When the user explicitly says that an attached document is something Atlas should learn, study, or treat as a skill:

- Atlas is instructed to extract concise reusable principles after analysis.
- Atlas checks memory first to reduce duplicate knowledge.
- Reusable principles are persisted via `memory_remember` as `kind=skill`.
- Learned knowledge stays in the current project unless the user explicitly asks for global knowledge.
- The original file is not copied wholesale into memory.
- Secrets remain excluded from memory.

## Deployment reliability fix

Railway watch patterns include Python source and tests (`*.py`, `tests/**`) in addition to the web app and requirements. Router/store/test changes will no longer be silently skipped by auto-deploy.

## Recovery

- Previous verified production application commit before this work: `70f61b4c04d8045754a418342fd74b094bf9d50f`.
- Previous verified Railway deployment: `9376d4e0-78aa-4d31-a732-f4965da485b9`.
- Restore service was not modified as part of this checkpoint.
