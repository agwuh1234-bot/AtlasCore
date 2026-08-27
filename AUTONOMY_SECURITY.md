# Autonomy safety boundaries

Autonomous execution is allowed for bounded, reversible engineering/browser work. Approval-required steps are represented explicitly and block only their dependent branch.

Never place credentials, cookies, browser storage state, API tokens, or encryption keys in task snapshots or logs. Browser storage state is handled only by `BrowserSessionStore` and encrypted at rest.

Retries are bounded and concurrency is bounded. Production lifecycle changes are tested on a branch before merge. A restart resumes from step boundaries, not from inside an unknown side effect; workers that perform writes should therefore be designed to be idempotent or verify state before retrying.

High-impact irreversible actions should use the approval worker rather than executing automatically.