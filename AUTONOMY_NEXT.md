# Next action

Open this branch as a PR against `main`. Let all autonomy workflows run. The lifecycle integration workflow applies `scripts/patch_main_autonomy.py` only inside the CI checkout and validates compilation plus the lifecycle contract. If green, apply the same guarded patch to the branch source, rerun CI, then merge. Do not bypass this gate.