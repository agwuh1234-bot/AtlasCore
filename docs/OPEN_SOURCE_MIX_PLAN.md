# Atlas Open-Source Mix Plan

## Goal
Keep AtlasCore as the control plane while using mature open-source engines for specialized execution.

## Keep in AtlasCore
- permissions and approval policy
- PostgreSQL task/checkpoint state
- project memory and user context
- task queue, retries and audit log
- model routing and budgets
- ChatGPT/Atlas bridge
- worker registry and health reporting

## Integrate as workers

### Browser Use — browser worker
Use for high-level autonomous web navigation, forms, extraction and authenticated browser workflows. Keep the existing Atlas BrowserExecutor as a deterministic fallback and for simple scripted actions.

Adapter contract:
`browser.agent(goal, session, limits) -> result + artifacts + verification evidence`

### OpenHands Software Agent SDK — coding worker
Use for repository-scale coding, tests, refactors and maintenance in an isolated workspace. Atlas remains responsible for permissions, branch policy, final verification and deploy approval.

Adapter contract:
`code.agent(goal, repo, branch, limits) -> commits/patch + tests + summary`

### LangGraph — evaluate, do not replace yet
Atlas already has a dependency graph, checkpoints, retries and approval semantics. Do not migrate the orchestration core immediately. First compare restart recovery, interrupts, subgraphs and persistence against the current Atlas engine. Adopt only if it removes substantial custom maintenance without weakening Atlas policy controls.

## Execution model
User/ChatGPT -> Atlas Planner -> durable task graph -> parallel workers -> Atlas Verifier -> retry/approval -> checkpoint -> next step -> result.

## Safety boundary
Workers never own global credentials or policy. Atlas passes only task-scoped capabilities. Payments, destructive production changes, account/security changes and other high-impact actions require an approval step. Prefer staging/branch changes and reversible operations.

## Rollout
1. Finish and merge current autonomy lifecycle integration.
2. Add a generic external-worker interface with capability metadata, timeout and artifact/result schema.
3. Add Browser Use behind a feature flag; benchmark against BrowserExecutor on a small canary suite.
4. Add OpenHands coding worker behind a feature flag; require branch isolation and tests.
5. Add verifier routing and automatic fallback between native and external workers.
6. Evaluate LangGraph with the same recovery/approval test suite before any orchestration migration.
7. Production canary, metrics, rollback, then enable selectively.

## Acceptance criteria
- restart resumes unfinished safe work
- independent workers can execute concurrently
- worker failure does not corrupt the task graph
- every external action is auditable
- credentials remain scoped
- verification occurs before a task is marked done
- feature flags permit instant fallback to native Atlas workers
