# PR checklist

- [ ] Autonomy unit tests green
- [ ] Runtime bootstrap tests green
- [ ] Guarded lifecycle patch applies exactly once per anchor
- [ ] Patched source compiles
- [ ] Lifecycle contract green
- [ ] Security/recovery/rollback contracts green
- [ ] No secrets or browser state committed
- [ ] Actual branch `main.py` patched only after first validation pass
- [ ] Full CI green after actual patch
- [ ] Merge only then
