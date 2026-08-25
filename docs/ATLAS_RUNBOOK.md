# Atlas Runbook

## Архитектура
- iPhone PWA → `/app-jobs` → `run_atlas`
- `run_atlas` → OpenAI + `web_search` / GitHub tools + optional Claude

## Auth
- app signed HttpOnly session
- `/bridge` — `ATLAS_BRIDGE_KEY`
- `/task/MCP` — `ATLAS_API_KEY`
- Значения секретов никогда не документировать

## Критичные файлы
- `main.py`
- `requirements.txt`
- `web/index.html`
- `web/app.js`
- `web/styles.css`
- `web/manifest.json`
- `web/sw.js`
- `web/icon.svg`
- `web/recovery.js`
- `web/ux.js`
- `web/status.js`
- `web/format.js`
- `web/format.css`

## Правила правок
- `main.py` никогда не переписывать целиком
- только маленькие уникальные `replace`
- после каждой правки читать фактический GitHub

## GREEN checkpoint
- Git SHA
- Railway SUCCESS
- runtime test
- manifest в `/Atlas Checkpoints`

## Текущая точка №10
- commit `4eab067af778aa457331e32372aaf6397647af4b`
- deployment `d9a284e8-0909-4c83-9c19-654fc1b31396`
- runtime `VOICE_EXPORT_RUNTIME_OK`

## Восстановление
- откатывать конкретные поврежденные файлы из последнего GREEN commit
- затем deploy
- `/health` и runtime

## Safety
- app write mode только на следующую команду
- read-only recovery можно повторить один раз
- write-задачи автоматически не повторять
- Claude: максимум 1 вызов на задачу
- не менять billing, платные сервисы и Apple signing без пользователя
