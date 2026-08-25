# Atlas GREEN checkpoint — mobile, memory, Shopify

Date: 2026-08-25 (UTC)

## Verified production state

- Application commit: `bf6d58a807451c4d1472a1068d48e379c217fe4d`
- Railway deployment: `bd6237c6-6e22-4d5c-b6ab-203881630e6c`
- AtlasCore service: `fd31f989-8c20-4e36-a5fd-84da595634a9`
- Production environment: `4b1d8f12-8514-40d2-8c45-4bab2f164b86`
- Postgres service: `da07eef4-2015-4d40-9285-ea9ed2e0e663`
- Postgres deployment: `7c28047b-5be1-432f-b0ce-a1123fe99bd6`
- GitHub Actions run: `32838051567` — success
- Railway deployment status: `SUCCESS`
- Runtime: application startup complete, Uvicorn listening on port 8080
- Health check: `GET /health` returned `200 OK`
- Pre-deploy suite: 18/18 tests passed
- Smoke check: `ATLAS_SMOKE_OK`
- PWA cache: `atlas-app-v14`

## Included in this checkpoint

- Stable iPhone app shell with fixed viewport, safe-area handling and keyboard-aware layout.
- Bottom navigation tabs: Chat, Projects, Memory, Actions and Plugins.
- Project creation and switching.
- Durable project-scoped memory stored in PostgreSQL.
- Safe automatic memory extraction for goals, decisions, preferences, constraints and project facts.
- Secret filtering prevents API keys, tokens and passwords from being saved as memory.
- Seeded Shopify operating knowledge and mobile-first Shopify rules.
- Shopify-aware project instructions and safety guardrails.
- Plugin registry with status and permission visibility.
- Action journal surfaced in the app.
- Memory deletion scoped to the owning project.
- Background task retention increased to 180 days by default.
- Expanded smoke checks and regression tests.

## Recovery points

Current GREEN application commit:

```
bf6d58a807451c4d1472a1068d48e379c217fe4d
```

Previous GREEN application commit and deployment:

```
52a0854f
652bce43
```

The preserved Railway service `AtlasCore-Restore` was not deleted or modified.

## Recovery procedure

1. Redeploy the current GREEN commit above.
2. Verify Postgres remains attached and `DATABASE_URL` resolves.
3. Confirm pre-deploy tests finish with `ATLAS_SMOKE_OK`.
4. Confirm runtime logs contain `Application startup complete`.
5. Confirm `GET /health` returns HTTP 200 before declaring recovery complete.
