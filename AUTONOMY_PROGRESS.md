# Progress

The engine implementation phase is complete enough for integration validation. The remaining sequence is deliberately narrow:

1. Open PR from `atlas/autonomy-lifecycle` to `main`.
2. Observe all CI results and fix failures on this branch.
3. Once green, apply the guarded lifecycle patch to this branch's `main.py`.
4. Rerun CI on the actual patched source.
5. Merge to `main` and verify Railway deployment.
6. Check `/health` autonomy state.
7. Run the read-only canary and restart-recovery test.
8. Only after those pass, expose authenticated Shopify automation to autonomous plans.
