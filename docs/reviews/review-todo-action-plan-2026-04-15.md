# Review TODO and Recommended Action Plan — 2026-04-15

Document version: 2026.04.15  
Last updated: 2026-04-15  
Status: Review Artifact  
Audience: Developers, reviewers, and maintainers

## Purpose

This document is the phase-based remediation plan derived from the 2026-04-15 end-to-end review. It now distinguishes:

- work completed during the review,
- validation used to close each phase,
- follow-up hardening work that remains useful but is no longer blocking.

---

## Phase Summary

| Phase | Goal | Status | Validation |
|---|---|---|---|
| Phase 1 | Confirm real code-doc and runtime drift | Complete | Review artifact set and targeted code inspection |
| Phase 2 | Repair deployment and auth defects blocking strict dedicated runtime | Complete | Compose config, live recreate, audit script, targeted tests |
| Phase 3 | Requalify live strict full-dedicated mission flow | Complete | Mission artifact qualification and dedicated canary evidence |
| Phase 4 | Close documentation and tooling drift around the fixed runtime | Complete | Documentation validation, targeted script tests, review artifact refresh |

---

## Completed Work by Phase

### Phase 1 — Review and defect confirmation

Completed:

- confirmed dedicated overlay drift on Redis cert mount and password defaults,
- confirmed dedicated topology stopped at agent 35 despite 38-agent claims,
- confirmed extractor docs under- and over-stated shipped AST behavior,
- confirmed operator-facing Mission Control and dashboard copy drift,
- confirmed strict dedicated auth path was incomplete,
- confirmed qualification tooling rejected valid `201 Created` mission responses.

Closure evidence:

- `docs/reviews/end-to-end-review-2026-04-15.md`
- targeted source inspection across compose, gateway, orchestrator, pod-worker, and docs

### Phase 2 — Runtime and deployment corrections

Completed:

- aligned dedicated Redis client cert mount with `deploy/.local/redis-certs`,
- aligned dedicated Redis password defaults with baseline compose,
- added dedicated services for Go, Haskell, and OCaml,
- wired `INTERNAL_SERVICE_API_KEY` into generated local key material,
- wired `INTERNAL_SERVICE_API_KEY` into `api-gateway`,
- added Redis TLS staging entrypoint to avoid Windows bind-mount key permission failures,
- expanded production review audit checks and regression tests.

Closure evidence:

- `python scripts/production_review_audit.py`
- `python -m pytest -q tests/scripts/test_generate_agent_service_keys.py tests/scripts/test_production_review_audit.py`
- strict dedicated stack reached healthy state after recreate

### Phase 3 — Live strict dedicated qualification

Completed:

- regenerated strict local service keys,
- recreated the full strict dedicated stack,
- revalidated live mission creation and mission completion,
- revalidated dedicated canary routing and pod-manager assignment.

Closure evidence:

- `docs/evidence/mission_artifact_qualification_full_dedicated_local_2026-04-15.json`
- `docs/evidence/dedicated_agent_canary_full_dedicated_local_2026-04-15.json`

### Phase 4 — Documentation and tooling alignment

Completed:

- updated README, architecture docs, implementation status docs, compose profile docs, runbook, service-key isolation docs, and onboarding docs,
- corrected Mission Control and dashboard runtime copy,
- fixed mission qualification and canary scripts to accept `201 Created`,
- refreshed the review artifact set so resolved findings are no longer presented as open defects.

Closure evidence:

- `python scripts/validate_documentation.py`
- `python -m pytest -q tests/scripts/test_mission_artifact_qualification.py tests/scripts/test_dedicated_agent_canary_rollout.py`

---

## Remaining TODOs

These are no longer break-fix items from the review. They are recommended hardening follow-ups.

| ID | Priority | Area | Recommendation | Done Criteria |
|---|---|---|---|---|
| FUP-1 | P2 | Dedicated smoke automation | Add a CI or scheduled smoke job that boots the strict full-dedicated profile and runs at least one live qualification path. | Overlay regressions fail before merge or in scheduled qualification. |
| FUP-2 | P2 | Compose parity guardrails | Extend static parity checks so shared baseline/overlay auth and TLS wiring cannot drift again. | CI fails when baseline and overlay diverge on required shared settings. |
| FUP-3 | P3 | Review artifact hygiene | Keep future review docs status-oriented so resolved findings are explicitly marked closed rather than copied forward as active defects. | New review artifacts separate open findings from historical context. |

---

## Recommended Execution Order for Follow-Up

1. Automate the strict full-dedicated smoke qualification path.
2. Expand compose parity checks beyond the current Redis/password/auth coverage.
3. Standardize the review closeout template so future review artifacts stay current.

---

## Exit Criteria

The 2026-04-15 review is considered closed because all blocking findings were corrected and revalidated:

1. strict full-dedicated compose config now matches corrected runtime assumptions,
2. live strict full-dedicated stack reached healthy state,
3. live mission artifact qualification passed,
4. live dedicated canary qualification passed,
5. canonical docs and operator-facing runtime copy now match the shipped implementation closely enough to remove the original review blockers.
