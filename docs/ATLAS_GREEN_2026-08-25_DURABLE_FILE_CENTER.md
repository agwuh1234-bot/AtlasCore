# Atlas GREEN checkpoint — durable file center

Date: 2026-08-25 (UTC)

## Verified production state

- Application commit: `8cbe991c7573c643d1e83000e4c80c05c711bae7`
- Pull request: `#6`
- GitHub Actions run: `32841870608` — success
- Railway deployment: `edd4de3c-65a2-4dc4-91de-5cad8ca79ef7`
- AtlasCore service: `fd31f989-8c20-4e36-a5fd-84da595634a9`
- Production environment: `4b1d8f12-8514-40d2-8c45-4bab2f164b86`
- Postgres service: `da07eef4-2015-4d40-9285-ea9ed2e0e663`
- Railway status: `SUCCESS`
- Runtime startup: complete
- Health check: `GET /health` returned `200 OK`
- Pre-deploy suite: 21/21 tests passed
- Smoke check: `ATLAS_SMOKE_OK`
- PWA cache: `atlas-app-v16`

## Included

- Durable `atlas_files` storage in PostgreSQL.
- Files are isolated by project.
- Identical content is deduplicated inside each project.
- Authenticated list/get/delete APIs with project scoping.
- New mobile Files tab.
- Up to four saved files can be selected for the next Atlas request.
- Successful task submission clears the temporary selection.
- Deletion requires an explicit confirmation in the UI.
- File Center is exposed in the plugin registry.
- Existing attachment and request limits remain enforced.

## Recovery

Redeploy this exact application commit:

```
8cbe991c7573c643d1e83000e4c80c05c711bae7
```

Previous verified application commit:

```
6aad7945b946c11f0901cdf337b0f7849523bf57
```

The preserved `AtlasCore-Restore` service was not deleted or modified.
