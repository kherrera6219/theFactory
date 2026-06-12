# Phase 18 - Reproducible Demo Missions and Launch Docs

## Status

**Local demo harness implemented. Live demo execution remains environment-gated.**

Phase 18 now defines three reproducible demo missions and a single harness that
can validate them offline or submit them to a live API Gateway. The dry-run path
is CI-safe and records the launch-demo manifest. The live path requires a running
stack and any provider credentials needed for LLM-backed generated output.

## Demo Missions

| Demo | Mission Type | Output Mode | Purpose |
|---|---|---|---|
| `build-new-python-cli` | `BUILD_NEW` | `FULL_BUILD` | Proves generated-output mission behavior. |
| `analyze-only-service-map` | `ANALYZE_ONLY` | `ANALYZE_ONLY` | Proves source intelligence without generated output. |
| `import-modernize-debug-repair` | `IMPORT_MODERNIZE` + `DEBUG_REPAIR` intent | `PATCH_PROPOSAL` | Proves source-bundle modernization and repair behavior. |

## Commands

```powershell
# CI-safe manifest validation
python scripts/demo_missions.py --dry-run --output-file docs/evidence/phase18_demo_missions_latest.json

# Live stack execution
python scripts/demo_missions.py --live --gateway-base-url http://localhost:8100 --output-file docs/evidence/phase18_demo_missions_live.json

# Make target
make demo
```

## Exit Criteria

- **Local Phase 18 evidence:** complete when `make demo` writes a passing
  dry-run evidence manifest and script tests pass.
- **Live launch demo:** complete only after the live command records all three
  missions reaching `COMPLETE` with PM/CEO/pod/specialist chain events. This
  remains blocked unless the runtime stack and provider-key configuration are
  available.
