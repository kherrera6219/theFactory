# Implementation Status

Document version: 2026.06.29-c
Last updated: 2026-06-29
Status: Canonical
Audience: Operators, developers, maintainers, and auditors

This document is the current-state snapshot for theFactory. When older phase
plans, ADRs, evidence files, or archived documents conflict with this file, this
file wins.

---

## Product Status

theFactory is an active local-first AI software factory application. It is not a
production-ready release.

The application currently includes:

- Mission Control Next.js operator UI
- API gateway
- orchestrator
- protocol-bus MCP
- pod workers and audit worker
- dedicated agent runtime containers
- PostgreSQL, Redis, Qdrant, Milvus, Neo4j, and MinIO data plane
- Prometheus/Grafana/Loki/Jaeger observability stack
- documentation validation and OpenAPI drift checks

---

## Current Proof Points

| Area | Current state |
|---|---|
| Runtime rebuild | Full dedicated-agent Docker stack rebuilt on 2026-06-27 |
| Rebuild readiness | API gateway, orchestrator, and Mission Control readiness passed |
| Backend/API mission path | Phase 13 smoke passed on 2026-06-27 |
| Smoke evidence | `docs/evidence/phase13_smoke_latest.json` |
| Passing smoke mission | `mission-b95ea912-94f8-4be8-8f7e-3cdce61cb7a7` |
| Mission state | `COMPLETE` |
| Chain trace | Required PM, CEO, pod-manager, and specialist events present |
| Artifacts | One build artifact retrieved; generated Python parsed successfully |
| Mission Control E2E | Phase 11 Playwright suite passed: 23 tests |
| Documentation controls | 78 metadata docs, 120 link docs, 17 docstring files, migration guide, and three diagram sets validated |
| OpenAPI drift | `scripts/export_openapi.py --check` passed in Phase 13 slice |
| Production audit | 22/23 checks pass; `INF-008` remains open |

---

## Remaining Release Gaps

| Gap | Required next step |
|---|---|
| Artifact correctness verification | Phase 1 done (format gate, per-criterion acceptance evaluation, and integrity-vs-correctness split in `equivalence_verifier.py` / `build_artifacts.py` / Mission Control); Phase 2 runnable-smoke verifier and a live re-run remain. See `UPDATE_PLAN_VERIFICATION_HARDENING_2026-06-29.md` |
| Non-ASCII artifact integrity | Localize and guard mojibake corruption in generated output |
| Lifecycle-engine reporting | Emit an authoritative `lifecycle_engine` field so v2 missions stop mislabeling as `LEGACY V1` |
| Phase 13 UI smoke | Submit and observe the mission path through Mission Control |
| Phase 13 failure injection | Interrupt protocol-bus MCP mid-mission and verify retry/resume or clean failure |
| Phase 13 provider fallback | Force primary provider failure and confirm fallback is used and recorded |
| Full validation | Run current `make validate` |
| Phase 8 coverage | Raise or explicitly defer `mission_flow_v2/` strict coverage target |
| Production audit | Fix `INF-008` internal service-key compose wiring finding |
| Provider configuration | Add real provider/key/model preflight and move provider/model choice into Settings/vault |
| Key hygiene | Rotate exposed provider keys before broader use |

---

## Shipped Defaults

| Setting | Default | Notes |
|---|---|---|
| `MISSION_FLOW_V2_ENABLED` | `true` | Primary runtime path |
| `LANGGRAPH_ENABLED` | `false` | Optional alternative lifecycle engine |
| `LANGGRAPH_CHECKPOINTER` | `none` | Postgres checkpointer requires explicit direct Postgres URL |
| `TESTDATA_AGENT_ENABLED` | `false` | Runtime QC support is opt-in |
| `RQCA_AGENT_ENABLED` | `false` | Runtime QC support is opt-in |
| `RQCA_ENFORCEMENT_ENABLED` | `false` | Advisory by default |
| `DEPABS_EXECUTION_ENABLED` | `false` | Dependency absorption execution remains opt-in |
| `LLM_PROVIDER` | `gemini` | Default provider route |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Default model for all agent routes |
| `OPENAI_MODEL` | `gpt-5.5` | Selectable non-default route |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | Selectable non-default route |
| `MILVUS_ENABLED` | `true` | Extended vector store enabled in base stack |
| `NEO4J_ENABLED` | `true` | Knowledge graph adapter enabled in base stack |
| `OBJECT_STORAGE_ENABLED` | `true` | MinIO/S3 artifact storage enabled in base stack |

---

## Recent Phase Summary

### Phase 13 Backend/API Smoke

Completed. Added smoke automation, fixed runtime-QC event literal drift, rebuilt
the full dedicated-agent Docker stack, and committed passing evidence from the
rebuilt runtime.

### Phase 12 Documentation Drift

Completed. Documentation validation, OpenAPI drift checks, public docstring
checks, migration-guide checks, and architecture diagram drift checks are wired.

### Phase 11 Mission Control E2E

Completed. Mission Control lint, unit tests, build, and 23 Playwright E2E tests
passed against the running backend stack in that review.

### Phase 10 Reliability

Completed for this pass. Baseline reliability evidence passed with 600 mission
requests, 99.00% success, and zero readiness failures.

### Phase 9 Security

Completed for tracked security-audit items. Remaining production-audit failure
is the unrelated `INF-008` compose/internal service-key wiring finding.

### Phase 8 Coverage

Still open. The global suite and configured coverage threshold passed in the
Phase 8 work, but the stricter audit target for `mission_flow_v2/` remains
below target and needs more scenario-level coverage or an explicit deferral.

---

## Source Of Truth

- Current app status: this file
- Active work: `docs/CURRENT_TODO.md`
- Handoff: `docs/HANDOFF_CURRENT.md`
- Docs landing page: `docs/README.md`
- Full doc map: `docs/DOCUMENTATION_INDEX.md`
- Historical material: `docs/archive/`
- Qualification evidence: `docs/evidence/`
