# Validation plan

PR validation is the next executable gate. The PR must point from `atlas/autonomy-lifecycle` to `main`. Inspect failures rather than merging around them. The integration workflow intentionally patches only its temporary checkout on the first pass. After that pass is green, apply the same deterministic patch to branch `main.py`, push, and require the workflows to validate the real integrated source before merge.
