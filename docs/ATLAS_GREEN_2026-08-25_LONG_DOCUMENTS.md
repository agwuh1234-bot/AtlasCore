# AtlasCore GREEN checkpoint — Long Document Mode

Date: 2026-08-25
Status: GREEN

## Verified production state

- Application commit: `7dd0fe30b82177fbe438071b36104026f297d597`
- Core long-document implementation: `7ba0f146977542305f76abecb7515f33a1ef07b6`
- Regression-test commit: `80556492946c93695cc62d15abeca967e101de8e`
- Railway deployment: `dc4712d3-5fd2-42d2-8d2d-4325570902ec` — SUCCESS
- Production tests: 40/40 passed
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

## Deployment reliability fix

Railway watch patterns now include Python source and tests (`*.py`, `tests/**`) in addition to the web app and requirements. Router/store/test changes will no longer be silently skipped by auto-deploy.

## Recovery

- Previous verified production application commit: `70f61b4c04d8045754a418342fd74b094bf9d50f`.
- Previous verified Railway deployment: `9376d4e0-78aa-4d31-a732-f4965da485b9`.
- Restore service was not modified as part of this checkpoint.
