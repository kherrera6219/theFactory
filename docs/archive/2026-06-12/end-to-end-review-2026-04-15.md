# End-to-End Review — theFactory

Document version: 2026.04.15  
Last updated: 2026-04-15  
Status: Review Artifact  
Audience: Developers, reviewers, and maintainers

## Review Date: 2026-04-15
## Reviewer: Codex
## Scope: Canonical docs, runtime code, deployment config, qualification scripts, Mission Control tests, and live local stack state

---

## Executive Summary

theFactory is a local-first multi-agent software-refinery platform. Missions enter through Mission Control or the API gateway, the orchestrator advances lifecycle state and routing, specialist workers produce structured extraction artifacts, and audit/build surfaces record verifiable outputs for operator review.

This review started with real code-doc drift and an unqualified strict full-dedicated topology. The repo now matches its corrected documentation materially better, and the strict local full-dedicated path was revalidated end to end on 2026-04-15.

There are no remaining open P0 correctness findings from this review. The remaining work is preventative hardening, not unresolved breakage.

---

## What the Application Does

theFactory accepts software missions, routes them through a 38-agent operating model, extracts source structure and concepts across supported languages, persists mission lifecycle state and audit evidence, and exposes that information through API and Mission Control operator surfaces.

At a product level it provides:

- mission intake and mission lifecycle orchestration,
- pod-worker or dedicated-worker language processing,
- audit and artifact recording,
- operational visibility across agents, projects, and system health,
- operator review surfaces for missions, builder review, repo intake, approvals, and settings.

---

## How the Application Does It

The runtime path is:

1. API Gateway accepts and normalizes mission intake.
2. Orchestrator persists mission state, selects the lifecycle engine, and emits state transitions.
3. Pod workers or dedicated workers consume Redis-backed mission state and perform language extraction.
4. Audit worker records verification and supporting evidence.
5. Mission Control and dashboard surfaces read gateway/orchestrator APIs for live operator views.

The default lifecycle path is Mission Flow V2. LangGraph is optional and disabled by default; legacy fallback is not the default runtime path. The active local data plane is PostgreSQL, Redis, and Qdrant, with Neo4j, Milvus, and object storage behind feature flags.

---

## Review Phases

| Phase | Goal | Result |
|---|---|---|
| Phase 1 | Validate code vs canonical docs and enumerate confirmed drift | Complete |
| Phase 2 | Repair runtime and deployment defects blocking strict dedicated qualification | Complete |
| Phase 3 | Revalidate strict full-dedicated mission flow with live evidence | Complete |
| Phase 4 | Reduce code-doc drift and close false-negative qualification tooling gaps | Complete |

---

## Validation Performed

| Validation | Result | Notes |
|---|---|---|
| `python scripts/validate_documentation.py` | PASS | Documentation links and metadata validate cleanly |
| `python scripts/production_review_audit.py` | PASS | 17/17 audit checks passed after remediation |
| `python -m pytest -q tests/scripts/test_generate_agent_service_keys.py tests/scripts/test_production_review_audit.py tests/scripts/test_mission_artifact_qualification.py tests/scripts/test_dedicated_agent_canary_rollout.py` | PASS | Qualification and audit script regressions covered |
| `npm run lint` in `apps/mission-control` | PASS | Previously validated during review |
| `npm run test` in `apps/mission-control` | PASS | Previously validated during review; 53/53 tests passed |
| `python scripts/mission_artifact_qualification.py --profile-label full-dedicated-local-2026-04-15 ...` | PASS | Evidence captured in `docs/evidence/mission_artifact_qualification_full_dedicated_local_2026-04-15.json` |
| `python scripts/dedicated_agent_canary_rollout.py --profile-label full-dedicated-local-2026-04-15 ...` | PASS | Evidence captured in `docs/evidence/dedicated_agent_canary_full_dedicated_local_2026-04-15.json` |
| `docker compose --env-file .env.agent-service-keys.local -f deploy/docker-compose.yaml -f deploy/docker-compose.full-dedicated-agents.yaml --profile full-dedicated-agents up -d --force-recreate` | PASS | Full strict dedicated stack reached healthy state locally |

---

## Resolved Findings

### R1 — Dedicated overlay Redis cert path drift

- **Status:** Resolved
- **Problem:** The dedicated overlay mounted Redis client certs from the stale `./redis/certs` path instead of `./.local/redis-certs`.
- **Fix:** Updated the overlay to use the current `.local` client-cert mount and aligned it with baseline compose behavior.
- **Validation:** Production review audit passes and merged compose output resolves the dedicated runtime to `./.local/redis-certs`.

### R2 — Dedicated overlay Redis password default drift

- **Status:** Resolved
- **Problem:** The dedicated overlay defaulted Redis auth to `dev-redis-password-change-me-32chars`, which diverged from baseline compose.
- **Fix:** Replaced the stale default with `CHANGE_ME_local_dev_redis_password_32chars`.
- **Validation:** Merged compose output now resolves the same default across baseline and overlay.

### R3 — Full dedicated topology stopped at agent 35

- **Status:** Resolved
- **Problem:** README and topology docs described a full isolated 38-agent runtime, but the dedicated overlay and `Makefile` omitted dedicated Go, Haskell, and OCaml services.
- **Fix:** Added `agent-36-go`, `agent-37-haskell`, and `agent-38-ocaml` to `deploy/docker-compose.full-dedicated-agents.yaml`, platform key wiring, and `Makefile`.
- **Validation:** `docker compose ... ps` shows all three dedicated services healthy in the strict full-dedicated profile.

### R4 — Strict dedicated launch generated keys but did not wire gateway internal auth

- **Status:** Resolved
- **Problem:** `scripts/generate_agent_service_keys.py` originally omitted `INTERNAL_SERVICE_API_KEY`, and `api-gateway` did not consume it from compose, so strict dedicated mission submission failed even after worker auth became healthy.
- **Fix:** Added `INTERNAL_SERVICE_API_KEY` generation, wired `INTERNAL_SERVICE_API_KEY` into `api-gateway` compose env, and added audit/test coverage.
- **Validation:** `docker inspect deploy-api-gateway-1` now shows `INTERNAL_SERVICE_API_KEY=...`, and live mission qualification passes.

### R5 — Redis TLS private-key bind mount failed on Windows live recreate

- **Status:** Resolved
- **Problem:** Redis could not read the TLS private key directly from the Windows bind mount during live stack recreation.
- **Fix:** Added `deploy/redis/entrypoint.sh` to stage TLS material into container-local temp storage with controlled ownership and permissions before starting Redis.
- **Validation:** `deploy-redis-1` reaches healthy state in the recreated strict full-dedicated stack.

### R6 — Qualification tooling falsely treated `201 Created` as failure

- **Status:** Resolved
- **Problem:** `mission_artifact_qualification.py` and `dedicated_agent_canary_rollout.py` rejected successful mission creation because the gateway returns `201 Created`, not `200`.
- **Fix:** Updated both scripts to accept `200` or `201` and added regression tests.
- **Validation:** Both live qualification scripts now pass against the live stack.

### R7 — Architecture and implementation docs drifted from extractor reality

- **Status:** Resolved
- **Problem:** `docs/ARCHITECTURE.md` understated Python extraction by describing the system as regex-only, while `docs/IMPLEMENTATION_STATUS.md` overstated JS/TS and Java AST support.
- **Fix:** Updated docs to describe the shipped model accurately: regex-first extraction, optional Python AST enhancement behind `PYTHON_AST_EXTRACTOR_ENABLED`, JS/TS and Java AST still stubbed.
- **Validation:** Canonical extractor docs now match `pod_worker` wiring and shipped modules.

### R8 — Operator-facing runtime copy drift

- **Status:** Resolved
- **Problem:** Mission Control agents page implied LangGraph-disabled missions use the legacy runtime path, and the dashboard still said Mission Control “will live” elsewhere.
- **Fix:** Updated Mission Control copy to state Mission Flow V2 remains the default when LangGraph is off, and updated dashboard copy to reflect Mission Control as the current operator UI.
- **Validation:** UI text now matches actual lifecycle routing and current product topology.

### R9 — Runbook and compose profile docs drift

- **Status:** Resolved
- **Problem:** Canonical operations docs referenced the wrong full-dedicated `make` targets and omitted the dedicated overlay from compose-profile guidance.
- **Fix:** Updated `docs/OPERATIONS_RUNBOOK.md`, `docs/COMPOSE_ENVIRONMENT_PROFILES.md`, `docs/AGENT_SERVICE_KEY_ISOLATION.md`, and `docs/DEVELOPER_ONBOARDING_GUIDE.md`.
- **Validation:** Docs now describe the actual strict full-dedicated launch path, recovery steps, and current key-generation behavior.

---

## Live Qualification Evidence

### Mission artifact qualification

- Evidence file: `docs/evidence/mission_artifact_qualification_full_dedicated_local_2026-04-15.json`
- Result:
  - `final_state=COMPLETE`
  - `assignment_present=true`
  - `logicnode_count=1`
  - required chain events present

### Dedicated agent canary

- Evidence file: `docs/evidence/dedicated_agent_canary_full_dedicated_local_2026-04-15.json`
- Result:
  - `final_state=COMPLETE`
  - expected pod manager observed: `AGENT-12-PODA-MGR`
  - `routing_enforced=true`
  - `rollback_recommended=false`

---

## Current Match Assessment

### Code vs docs

The repo is now materially aligned on:

- what the platform does,
- how missions move through the runtime,
- the default Mission Flow V2 lifecycle path,
- the shipped extractor behavior,
- the strict full-dedicated topology and launch method.

### Code vs live runtime

The strict local full-dedicated profile was revalidated live after remediation. The stack reached healthy state, mission submission succeeded, and both artifact and canary qualification passed. The major mismatches found during review were implementation defects and tooling false negatives; both classes are now corrected.

---

## Remaining Follow-Up

No open blocking findings remain from this review.

Recommended future hardening:

- add a CI or scheduled smoke qualification for the strict full-dedicated profile,
- keep review artifacts status-oriented so resolved findings do not remain phrased as open defects,
- continue expanding automated parity checks between baseline and overlay compose files.

