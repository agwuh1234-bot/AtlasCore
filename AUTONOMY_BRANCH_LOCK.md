# Branch discipline

`atlas/autonomy-lifecycle` is the integration branch. Do not fast-forward `main` to this branch merely because the modules compile. Use a PR so workflow results are attached to the exact head commit. Apply the guarded `main.py` patch only after the first validation pass, then require a second green pass on the actual integrated source before merge.