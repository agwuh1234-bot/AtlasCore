# Atlas GREEN checkpoint — PostgreSQL durable core

Date: 2026-08-25 (UTC)

## Production

- Repository: `agwuh1234-bot/AtlasCore`
- Branch: `main`
- Application commit: `52a0854f33f9b6b5698fc00214c3bb3e58c3ade2`
- Railway project: `tranquil-reflection` (`0ae6cdbb-41ad-4926-b771-93c3012cf186`)
- Environment: `production` (`4b1d8f12-8514-40d2-8c45-4bab2f164b86`)
- AtlasCore service: `fd31f989-8c20-4e36-a5fd-84da595634a9`
- AtlasCore deployment: `652bce43-2d3c-46e8-b479-3f59c715a1ab`
- AtlasCore deployment status: `SUCCESS`
- Public domain: `atlascore-production.up.railway.app`

## Durable storage

- PostgreSQL service: `da07eef4-2015-4d40-9285-ea9ed2e0e663`
- PostgreSQL deployment: `7c28047b-5be1-432f-b0ce-a1123fe99bd6`
- PostgreSQL status: `SUCCESS`
- Persistent volume: `1977d1cc-5a18-4603-9d3b-07bb744a98c6`
- AtlasCore variable: `DATABASE_URL = ${{Postgres.DATABASE_URL}}`

## Included capabilities

- PostgreSQL-backed durable jobs with restart recovery
- Project-scoped history and long-term memory
- Model router with fast / strong / fresh-web lanes
- Daily and per-task budget limits
- Real action audit records
- Project switcher and budget status UI
- Automated Atlas CI and production pre-deploy smoke checks

## Verification

- GitHub Atlas CI: `success`
- Production pre-deploy: 13/13 unit tests passed
- Production marker: `ATLAS_SMOKE_OK`
- FastAPI startup: complete
- Railway healthcheck: `/health` passed
- Runtime error scan after startup: no `NameError`, traceback, or background-job errors
- Pre-deploy unit tests are isolated from production PostgreSQL and use a unique temporary SQLite database

## Pull requests

- #1 — durable jobs, project memory, router and budgets
- #2 — isolate pre-deploy tests from production database
- #3 — fix runtime regex dependency and add regression test

## Recovery

The last pre-feature production commit is
`644255765072cf8879960c1a821ec317c109d1ce`, with successful deployment
`1b669f0f-661e-4828-a8dc-309c95013cbf`.

The current GREEN production checkpoint is the application commit and deployment recorded above.
Do not delete the preserved `AtlasCore-Restore` service
(`71064a00-840c-46cc-ba9b-86d5f77f0e23`) without an explicit recovery decision.
