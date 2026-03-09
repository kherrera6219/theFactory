# Long-Duration Reliability Qualification

Last updated: 2026-03-03

## Purpose

Define and record sustained-load plus recovery qualification for the core mission path.

## Tooling

- `scripts/reliability_qualification.py`
- `scripts/reliability_qualification.ps1`
- `make reliability`

## Qualification Scenario (Phase 10 Baseline)

Run date: 2026-03-03

Command:

```bash
python scripts/reliability_qualification.py \
  --duration-seconds 180 \
  --requests-per-second 1.5 \
  --concurrency 10 \
  --min-success-rate 99 \
  --max-p95-seconds 2.5 \
  --max-readiness-failures 30 \
  --max-consecutive-readiness-failures 8 \
  --failure-command "docker compose -f deploy/docker-compose.yaml restart orchestrator" \
  --failure-inject-after-seconds 60 \
  --output-file docs/evidence/reliability_qualification_baseline_2026-03-03.json
```

## Baseline Results

- Total mission requests: `270`
- Mission success rate: `100.00%`
- Latency p50: `0.046s`
- Latency p95: `0.051s`
- Latency max: `0.054s`
- Readiness checks: `72` total, `2` failed
- Max consecutive readiness failures: `1`
- Failure injection: orchestrator restart executed, exit code `0`
- Recovery probe: `passed` in `3` polls
- Overall result: `PASS`

Evidence artifact:

- `docs/evidence/reliability_qualification_baseline_2026-03-03.json`

## Re-run Guidance

1. Ensure application stack is up:
   - `docker compose -f deploy/docker-compose.yaml up -d`
2. Run qualification:
   - `powershell -ExecutionPolicy Bypass -File scripts/reliability_qualification.ps1 -InjectOrchestratorRestart`
3. Store output JSON under `docs/evidence/` and update this document with current baselines.
