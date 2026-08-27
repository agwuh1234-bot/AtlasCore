from pathlib import Path

p = Path("main.py")
s = p.read_text(encoding="utf-8")

replacements = [
    (
        "from atlas_push import PushService\n",
        "from atlas_push import PushService\nfrom atlas_autonomy_runtime import (\n    build_autonomy_runtime,\n    start_autonomy_runtime,\n    stop_autonomy_runtime,\n)\n",
    ),
    (
        "BUDGET = BudgetController(STORE, openai_client)\n",
        "BUDGET = BudgetController(STORE, openai_client)\nAUTONOMY_RUNTIME = build_autonomy_runtime(STORE)\n",
    ),
    (
        "    APP_JOB_WORKER = asyncio.create_task(_app_job_worker())\n    try:\n",
        "    APP_JOB_WORKER = asyncio.create_task(_app_job_worker())\n    resumed = await start_autonomy_runtime(AUTONOMY_RUNTIME)\n    logger.info(\"Atlas autonomy runtime online; resumed=%s\", resumed)\n    try:\n",
    ),
    (
        "        APP_JOB_WORKER = None\n        STORE.close()\n",
        "        APP_JOB_WORKER = None\n        await stop_autonomy_runtime(AUTONOMY_RUNTIME)\n        STORE.close()\n",
    ),
    (
        '        "jobs": {"max_active": APP_JOB_MAX_ACTIVE},\n',
        '        "jobs": {"max_active": APP_JOB_MAX_ACTIVE},\n        "autonomy": AUTONOMY_RUNTIME.health(),\n',
    ),
]

for old, new in replacements:
    count = s.count(old)
    if count != 1:
        raise SystemExit(f"Refusing patch: expected exactly one match, got {count}: {old[:80]!r}")
    s = s.replace(old, new, 1)

p.write_text(s, encoding="utf-8")
print("main.py autonomy lifecycle patch applied")
