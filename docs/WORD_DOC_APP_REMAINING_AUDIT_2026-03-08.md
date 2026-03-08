# Word-Doc App Remaining Audit (2026-03-08)

## Scope

Audited all 15 `.docx` files in-repo:

- Root docs: `HGR_*`, `HolyGrail_*`
- Legacy profile batches: `legacy documentation/*.docx`

Extraction evidence: `docs/evidence/word_doc_extraction_2026-03-08.json`.

## High-Level Status

The app is materially aligned with the current canonical runtime baseline (v1.1 mission lifecycle, 35-agent registry, LangGraph + recovery, artifact guardrails, OIDC/auth matrix, canary trend qualification, tracing, and hardened compose baseline).  

Remaining work is mostly **word-doc strict-compliance** (legacy/aspirational requirements) rather than production blockers in the current roadmap baseline.

Resolved on 2026-03-08 after this audit:

- strict compose hardening baseline now includes `cap_drop`, zero `cap_add`, and `oom_score_adj`
- `dev` / `staging` / `prod` compose overlays now exist and validate
- preview-model promotion governance now blocks non-production lifecycle stages and defaults Gemini routes to stable versions
- canonical legacy profile mapping index is now published
- weekly qualification cadence now has a scheduled workflow plus machine-readable threshold summary for release gating

## Remaining Items (What Is Left)

## 1) Mission Flow v2 Full Adoption (Not Yet Runtime Canonical)

- Word docs (`HGR_Mission_Flow_v2.docx`) describe 11-phase microstate runtime.
- Current canonical runtime remains v1.1 (`QUEUED -> RUNNING -> VERIFIED -> COMPLETE`) with checkpoint events.
- Required if strict v2 compliance is desired:
  - mission/event schema migration for 11 phases
  - API/UI timeline compatibility migration
  - full regression/e2e coverage for v2 microstates

## 2) Full 35 Dedicated-Agent Container Topology

- Checklists describe per-agent container isolation.
- Current runtime uses condensed workers + dedicated pod-manager profile expansion (not 35 dedicated containers).
- Required if strict checklist interpretation is desired:
  - 35 dedicated services in compose profile
  - scheduler/routing contracts and load tests for dedicated topology

## 3) Per-Agent API Key Isolation at Runtime

- Word checklists call for isolated credentials per agent.
- Current runtime supports keyed auth and has reserved per-agent env slots, but execution still relies on shared worker/internal keys in major flows.
- Required:
  - enforce per-agent key usage in runtime paths
  - key-rotation runbook + conformance test

## 4) Extra Container Hardening Controls from Checklist

- Completed 2026-03-08.
- `cap_drop: [ALL]`, zero `cap_add`, and `oom_score_adj` policy are now present in compose baseline.
- Seccomp stance is explicitly documented per environment in `docs/COMPOSE_ENVIRONMENT_PROFILES.md`.

## 5) Environment Compose Overlay Set

- Completed 2026-03-08.
- `deploy/docker-compose.dev.yaml`, `deploy/docker-compose.staging.yaml`, and `deploy/docker-compose.prod.yaml` now exist.

## 6) Legacy Profile Canonicalization Debt

- Completed 2026-03-08.
- Canonical mapping index is now published in `docs/LEGACY_PROFILE_ID_MAPPING_INDEX.md`.

## 7) Model Lifecycle Governance for Preview Models

- Completed 2026-03-08.
- Promotion gate now consumes model inventory and blocks preview/experimental lifecycle stages.
- Runtime Gemini defaults now point to production-approved stable routes.

## 8) Operational Cadence (Roadmap)

- Completed 2026-03-08 for current baseline.
- Weekly qualification workflow and machine-readable threshold summary are now wired into release promotion policy evaluation.
