# Integration scripts

`patch_main_autonomy.py` is intentionally fail-closed. It patches only exact, unique anchors in `main.py`; if AtlasCore changes and an anchor is missing or duplicated, it exits non-zero and leaves the source untouched. CI uses it in an ephemeral checkout before any production merge.