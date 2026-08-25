# Atlas GREEN checkpoint — diagnostics, permissions and voice

Date: 2026-08-25 (UTC)

## Verified production state

- Application commit: `6aad7945b946c11f0901cdf337b0f7849523bf57`
- Pull request: `#5`
- GitHub Actions run: `32838983982` — success
- Railway deployment: `b7b51196-a6f3-4787-99f4-51128136426c`
- AtlasCore service: `fd31f989-8c20-4e36-a5fd-84da595634a9`
- Production environment: `4b1d8f12-8514-40d2-8c45-4bab2f164b86`
- Postgres service: `da07eef4-2015-4d40-9285-ea9ed2e0e663`
- Railway status: `SUCCESS`
- Runtime: application startup complete; Uvicorn listening on port 8080
- Health check: `GET /health` returned `200 OK`
- Pre-deploy suite: 20/20 tests passed
- Smoke check: `ATLAS_SMOKE_OK`
- PWA cache: `atlas-app-v15`

## Included in this checkpoint

- Authenticated system diagnostics for OpenAI, GitHub, PostgreSQL, Web, Railway, Claude, Shopify and Make.
- System status and permission levels displayed inside the mobile Plugins tab.
- Four permission levels: read, safe automatic work, confirmed writes, and separately confirmed dangerous/expensive actions.
- Explicit policy that deletion, publication, payments, irreversible or expensive actions require a clear textual confirmation even when write mode is enabled.
- Hands-free voice conversation loop on supported iPhone browsers.
- Dedicated “Стоп голос” control.
- Voice mode remains opt-in and session-scoped.
- PWA cache refreshed to version 15.
- Regression coverage for system diagnostics, permission policy and voice controls.

## Recovery

Redeploy this exact application commit:

```
6aad7945b946c11f0901cdf337b0f7849523bf57
```

If this checkpoint must be rolled back, the previous verified application point is:

```
bf6d58a807451c4d1472a1068d48e379c217fe4d
```

The preserved Railway service `AtlasCore-Restore` was not deleted or modified.
