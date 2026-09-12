# Interaction Pacing Engine

`modules/human_engine/` is an optional UI-interaction pacing layer for FB Automation.
It does not change group/page/comment/join business rules and it does not spoof browser fingerprints.

## Scope

- Exact-text typing with configurable timing; typo insertion remains disabled in production bridge.
- Kinematic pointer primitives for ordinary UI interactions.
- Kinetic scrolling with bounded motion.
- Deterministic per-account profiles, keyed by the real automation account/profile id.
- Legacy behavior remains authoritative fallback in `utils.py`.

## Safety and rollout

`ENABLE_ADVANCED_HUMAN_ENGINE` defaults to `false` and is read when `utils.py` is imported.
Changing the environment flag requires a process restart.
When enabled, the bridge logs only operation/status/account id and fallback reason class; it does not log typed content.

No CDP hiding, `navigator.webdriver` modification, plugin spoofing, WebGL/GPU spoofing, or other fingerprint-evasion code is part of this module.

## Verification

Run module tests:

```powershell
.\runtime\venv\Scripts\python.exe -m unittest discover -s modules\human_engine\tests -p "test_*.py"
```

Run the complete project regression suite with the feature flag both disabled and enabled before release.
