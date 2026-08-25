# Atlas Runbook

## Архитектура

- iPhone PWA → /app-jobs → durable worker → run_atlas
- jobs, projects, memory, usage and action log → AtlasStore
- DATABASE_URL / ATLAS_DATABASE_URL → PostgreSQL
- без PostgreSQL используется локальный SQLite fallback для разработки; он не переживает Railway redeploy
- run_atlas → model router → OpenAI + optional web_search, GitHub tools and Claude
- project id scopes response chain, local PWA history, durable job history and memory

## Durable jobs

- maximum three queued/running jobs across the shared database
- worker claim is transactional; PostgreSQL uses FOR UPDATE SKIP LOCKED
- heartbeat every 10 seconds; a lease is stale after 90 seconds
- read-only text job may be queued once after an interrupted worker
- write-mode or attachment jobs are never automatically replayed
- cancellation is stored first; a late worker result cannot overwrite it
- completed jobs are retained for 30 days

## Memory and projects

Default projects: General, Atlas, Shopify and Промо.

- memory_search reads only the current project
- memory_remember stores durable facts, decisions, preferences and tasks
- explicit “запомни/remember” requests are stored automatically
- never store secrets in project memory
- /app-projects/{id}/history restores finished work on a new device/session

## Router and budget guard

Defaults can be overridden with Railway variables:

- ATLAS_MODEL_FAST=gpt-5.6-luna
- ATLAS_MODEL_STRONG=gpt-5.6-sol
- ATLAS_MODEL_FALLBACK=gpt-5.4-mini
- ATLAS_DAILY_BUDGET_USD=3.00
- ATLAS_TASK_BUDGET_USD=0.60
- ATLAS_MAX_INPUT_TOKENS=50000
- ATLAS_CLAUDE_DAILY_LIMIT=3

The router uses the fast lane by default, the strong lane for code/complex reasoning, and enables web search only for fresh information. A conservative worst-case reservation is written before an OpenAI request and converted to actual usage afterward.

## Auth

- app: signed HttpOnly session
- /bridge: ATLAS_BRIDGE_KEY
- /task and MCP: ATLAS_API_KEY
- never document secret values

## Critical files

- main.py
- atlas_store.py
- atlas_router.py
- requirements.txt
- smoke_check.py
- tests/
- web/index.html
- web/app.js
- web/projects.js
- web/projects.css
- web/styles.css
- web/manifest.json
- web/sw.js
- web/icon.svg
- web/recovery.js
- web/ux.js
- web/status.js
- web/format.js
- web/format.css

## Change rules

- never reconstruct main.py or web/recovery.js after damage
- restore the exact file from the latest GREEN commit
- make small unique patches and verify the actual GitHub content
- a GREEN checkpoint requires Git SHA, Railway SUCCESS, /health, runtime checks and a manifest in Atlas Checkpoints

## Production baseline before durable-state rollout

- commit 644255765072cf8879960c1a821ec317c109d1ce
- Railway deployment 5bec3afd-98a7-459c-bda1-b38f63173b05
- status SUCCESS
- PWA cache atlas-app-v12

## Safety

- app write mode applies only to the next command
- Claude: at most one call per task and three calls per UTC day by default
- do not create billable infrastructure, change billing or perform Apple signing without the user
