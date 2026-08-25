# Atlas GREEN checkpoint — Web Push

Date: 2026-08-25 (UTC)

## Verified production state

- Application commit: `cd50098b2f6dc3f04b2ae42cddb74bb05c64e7a1`
- Pull request: `#7`
- GitHub Actions run: `32844400220` — success
- Railway deployment: `1226115c-60f4-4958-ad44-89d699888c6f`
- AtlasCore service: `fd31f989-8c20-4e36-a5fd-84da595634a9`
- Production environment: `4b1d8f12-8514-40d2-8c45-4bab2f164b86`
- Postgres service: `da07eef4-2015-4d40-9285-ea9ed2e0e663`
- Railway status: `SUCCESS`
- Replica: 1/1 running
- Runtime startup: complete
- Health check: `GET /health` returned `200 OK`
- Pre-deploy suite: 24/24 tests passed
- Smoke check: `ATLAS_SMOKE_OK`
- PWA cache: `atlas-app-v17`

## Included

- Server-generated P-256 VAPID key pair.
- VAPID private material remains server-side and is persisted in PostgreSQL.
- Authenticated push subscription, unsubscribe, status and test endpoints.
- Push subscriptions are stored durably and refreshed idempotently.
- Expired 404/410 subscriptions are disabled automatically.
- Successful background jobs trigger a privacy-safe generic completion notification.
- Installed iPhone PWA can subscribe from the existing Notifications button.
- A test notification is sent immediately after successful subscription.
- Service Worker receives push messages while the PWA is closed and opens the matching job URL.
- No Apple Developer account or paid push provider is required.

## User gesture still required

Apple requires the user to grant notification permission from the installed PWA. Open Atlas from the Home Screen and tap:

```
Settings → Включить Push-уведомления
```

## Recovery

Redeploy this exact application commit:

```
cd50098b2f6dc3f04b2ae42cddb74bb05c64e7a1
```

Previous verified application commit:

```
8cbe991c7573c643d1e83000e4c80c05c711bae7
```

The preserved `AtlasCore-Restore` service was not deleted or modified.
