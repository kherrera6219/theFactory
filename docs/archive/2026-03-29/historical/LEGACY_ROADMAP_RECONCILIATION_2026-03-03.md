# Legacy Roadmap and Runtime Port Reconciliation (2026-03-03)

## Purpose

Reconcile legacy planning artifacts in `legacy documentation/` with the active delivery baseline in `docs/ROADMAP.md` and current runtime behavior.

## Canonical Runtime Port Policy (Mission Control)

- Docker-host access (default local stack): `http://localhost:3100`
- Direct Next.js development mode (`cd apps/mission-control && npm run dev`): `http://localhost:3000`
- Container-internal app port remains `3000`; Docker mapping exposes host `3100`.

Port references in legacy design documents that use only `3000` are historical/dev-mode assumptions and are not the canonical host-port default for the Docker stack.

## Legacy Phase-4 Advanced Scope Disposition

Source baseline: `legacy documentation/04_Product_Roadmap_Phasing_Strategy.md`.

| Legacy theme | Disposition | Rationale | Current tracking |
|---|---|---|---|
| Self-update/autonomous quarterly model evolution | Deferred | Requires additional governance controls, rollout safety, and measurable risk boundaries not yet prioritized for production baseline. | Future roadmap candidate after remaining P1 work. |
| 20-language expansion and large specialist growth | Deferred | Current delivery focus is reliability/security hardening and operational completeness over language-surface expansion. | Future roadmap candidate. |
| Hosted cloud multi-tenant offering | Deferred | Current deployment target is local-first runtime with enterprise hardening controls. | Future strategy decision. |
| Third-party agent marketplace | Deferred | Requires trust, curation, signing, and ecosystem governance beyond current baseline scope. | Future strategy decision. |
| Multi-target distributed execution (GPU/TPU/FPGA, distributed missions) | Deferred (R&D) | High-complexity optimization path with no committed near-term milestone. | Research backlog only. |
| Revenue/investment projections in legacy roadmap | Deprecated | Financial projections are not used as executable engineering commitments in canonical planning. | Not tracked in canonical technical roadmap. |

## Adopted Scope from Legacy Plan

Core concepts from legacy Phases 1-3 are adopted and represented in canonical docs:
- multi-agent runtime and pod architecture
- mission lifecycle orchestration
- CI/test/observability/reliability hardening controls

See:
- `docs/ROADMAP.md`
- `docs/PRODUCTION_PHASE_PLAN.md`
- `docs/COMPLETION_TODO_2026-03-02.md`

## Decision Rule

Canonical execution authority is the `docs/` set. Legacy documents remain historical design references unless explicitly promoted into canonical docs via a dated reconciliation note.
