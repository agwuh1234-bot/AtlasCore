# AtlasCore GREEN checkpoint — Smart Durable Memory

Date: 2026-08-25
Status: GREEN

## Verified production state

- Application commit: `70f61b4c04d8045754a418342fd74b094bf9d50f`
- Pull request: #9 (`codex/smart-memory`)
- GitHub Actions run: `32862193190` — success
- Railway deployment: `9376d4e0-78aa-4d31-a732-f4965da485b9` — SUCCESS
- Production tests: 35/35 passed
- Smoke check: `ATLAS_SMOKE_OK`
- Railway health check: `GET /health` returned HTTP 200
- PWA cache version: v19

## Smart memory included

- Durable PostgreSQL memory remains independent of the phone and application restarts.
- Retrieval is ranked by query relevance, memory type importance, and recency.
- Cosmetic duplicates are reused instead of creating another record.
- Global preferences from `project-general` are included in every project context.
- Project-specific facts and tasks remain isolated between projects.
- Existing memories can be edited without changing their stable identity.
- The mobile Memory screen includes search, project/global scope, health, edit, and confirmed delete.
- No automatic memory deletion and no additional paid model calls.

## Safety and recovery

- Secrets and payment credentials remain prohibited by policy.
- Deletes require explicit confirmation and remain project-scoped.
- Previous verified application commit: `222df4fc9d82b8c31ab04f8105f9f512f0082dab`
- `AtlasCore-Restore` remains preserved and was not modified or deleted.
