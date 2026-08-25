# AtlasCore GREEN checkpoint — Durable Automations

Date: 2026-08-25
Status: GREEN

## Verified production state

- Application commit: `222df4fc9d82b8c31ab04f8105f9f512f0082dab`
- Pull request: #8 (`codex/durable-scheduler`)
- GitHub Actions run: `32861252460` — success
- Railway deployment: `9e2133e7-1a2f-4ec7-9c74-2265d626a2d2` — SUCCESS
- Production tests: 30/30 passed
- Smoke check: `ATLAS_SMOKE_OK`
- Production health check: `GET /health` returned HTTP 200
- PWA cache version: v18

## Durable Automations included

- Persistent schedules in PostgreSQL.
- Schedule types: once, daily, weekly.
- IANA timezones with DST-aware calculations; default timezone is `Europe/Berlin`.
- Atomic due-schedule claiming with leases, advisory lock, and `FOR UPDATE SKIP LOCKED`.
- Multiple app replicas cannot enqueue the same occurrence twice.
- Failed queue attempts are retried later.
- One-time schedules disable after firing; recurring schedules advance automatically.
- Project-scoped list/create/pause/resume/delete API.
- Mobile “Авто” tab with weekday selector, next/last run, pause/resume, and delete actions.

## Safety boundary

Scheduled executions are read-only text tasks:

- `allow_writes: false`
- no attachments
- no Claude review
- no code or data mutation without an interactive approval flow

## Infrastructure references

- Railway project: `tranquil-reflection` (`0ae6cdbb-41ad-4926-b771-93c3012cf186`)
- Production environment: `4b1d8f12-8514-40d2-8c45-4bab2f164b86`
- AtlasCore service: `fd31f989-8c20-4e36-a5fd-84da595634a9`
- PostgreSQL service: `da07eef4-2015-4d40-9285-ea9ed2e0e663`
- PostgreSQL deployment: `7c28047b-5be1-432f-b0ce-a1123fe99bd6`

## Recovery

The previous verified application commit is:

`cd50098b2f6dc3f04b2ae42cddb74bb05c64e7a1`

The separate Railway service `AtlasCore-Restore` is intentionally preserved and was not modified or deleted.
