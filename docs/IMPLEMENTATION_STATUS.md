# Implementation Status

Document version: 2026.07.02
Last updated: 2026-07-02
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
| Runtime validation | Full-dedicated stack evidence refreshed on 2026-06-30 |
| Rebuild readiness | API gateway and orchestrator readiness passed in the current smoke evidence |
| Backend/API mission path | Phase 13 smoke passed on 2026-06-30 |
| Smoke evidence | `docs/evidence/phase13_smoke_latest.json` |
| Passing smoke mission | `mission-ac933664-bda8-4acf-b265-10171c2ccdf6` |
| Mission state | `COMPLETE` |
| Chain trace | Required PM, CEO, pod-manager, and specialist events present |
| Artifacts | One build artifact retrieved; generated Python parsed successfully |
| Non-ASCII artifact integrity | Phase 3 smoke `mission-bd5369ec-3777-4099-89fe-81699289a29d` preserved 28 non-ASCII characters through codegen, packaging, and storage readback |
| Non-ASCII evidence | `docs/evidence/phase3_non_ascii_smoke_latest.json` |
| Mission Control E2E | Phase 11 Playwright suite passed: 23 tests |
| Documentation controls | 75 metadata docs, 117 link docs, 17 docstring files, migration guide, and three diagram sets validated |
| OpenAPI/API type drift | Generated API types include `MissionRecord.lifecycle_engine`; latest drift/security gate fixes were locally validated |
| Production audit | 23/23 checks pass; `INF-008` closed |
| Security alert remediation | CodeQL #337-#338 fixed in UI/RQCA paths; Trivy #330-#336 addressed by refreshed Python service base-image digests and verified rebuilt orchestrator OpenSSL `3.0.20-1~deb12u2` |
| Phase 8 Mission Flow v2 coverage | Isolated suite: 81 passed, 91.56% line / 71.69% branch; broader related suite: 170 passed, 92.43% line / 74.70% branch |
| Repository ZIP import | ZIP archive core, multipart import/review routes, and `/repo` ZIP UI are locally validated; Mission Control lint, 87/87 Vitest, 22/22 focused repo tests, and targeted repo-intake Playwright e2e passed |
| Mission Control UX lock-in | PM clarification cards/defaults, Live Progress indicators, local output-folder status/open actions, VS Code launch, and Continue with PM context loading are implemented and rebuilt into `deploy-mission-control:latest` / `deploy-orchestrator:latest`; post-restart Angular Snake browser proof remains pending |

---

## Remaining Release Gaps

| Gap | Required next step |
|---|---|
| Artifact correctness verification | Phase 1+2 code done (format gate, per-criterion acceptance evaluation, integrity-vs-correctness split, RQCA runnable-smoke evidence, authoritative `lifecycle_engine`); full validation and live Pong-style rerun remain. See `UPDATE_PLAN_VERIFICATION_HARDENING_2026-06-29.md` |
| Non-ASCII artifact integrity | Phase 3 code adds non-ASCII regression coverage, packaging-time mojibake guard/repair before digest, codegen/package/storage-readback trace, lifted PM clarifying-question/context truncation, and passing live non-ASCII evidence at `docs/evidence/phase3_non_ascii_smoke_latest.json` |
| Lifecycle-engine reporting | Current code emits authoritative `lifecycle_engine` through orchestrator, gateway, chain trace, and Mission Control; live Mission Detail rerun remains |
| Phase 13 UI smoke | Submit and observe the mission path through Mission Control |
| Mission Control UX lock-in proof | After restart, run a real browser mission for a modern Angular Snake game with `start.bat` and confirm PM clarification/defaults, live progress, output-folder actions, and Continue with PM |
| Phase 13 failure injection | Interrupt protocol-bus MCP mid-mission and verify retry/resume or clean failure |
| Phase 13 provider fallback | Force primary provider failure and confirm fallback is used and recorded |
| Full validation | Run current `make validate` |
| Phase 8 branch coverage | Raise remaining `mission_flow_v2/` branch coverage or explicitly defer the old 85% branch target; line coverage now clears 90% |
| Provider configuration | Add real provider/key/model preflight and move provider/model choice into Settings/vault |
| Key hygiene | Rotate exposed provider keys before broader use |
| Repository knowledge ingestion | Add mission index guard, repo knowledge ingestion, and PM/pod-worker repository context loading after ZIP launch |

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

### Mission Control UX Lock-In

Completed for the current pass. Mission Control now displays PM clarification
questions as actionable cards with recommended defaults, exposes clearer
mission-progress states and next actions, shows local output-folder path/status
with Copy Path / Open Folder / VS Code actions, and preloads prior mission
output/artifact context when continuing with PM. Orchestrator PM contract
normalization now asks clarifying questions for underspecified interactive
apps/games, and expected generated-output missions cannot complete without a
durable generated output artifact. Focused frontend/backend tests, Mission
Control build/lint, compose service graph resolution, and Docker rebuilds for
`mission-control` and `orchestrator` passed. Evidence:
`docs/evidence/mission_control_ux_lockin_2026-07-02.md`.

### Repository ZIP Import Hardening

Completed for the current pass. Mission Control removed committed pytest temp
artifacts, hardened ZIP upload/review validation, requires archive-hash binding
for reviews, preserves selected files outside the display slice, and migrated
the `/repo` page plus e2e coverage to local ZIP FormData import/review.

### Security Alert Remediation

Completed for the current pass. RQCA HTML smoke now uses parser-based extraction
instead of a filtering regexp, Mission Control file previews are raster-only
with sanitized filenames, and Python service Dockerfiles are pinned to a current
`python:3.11-slim-bookworm` digest whose rebuilt orchestrator image reports
OpenSSL `3.0.20-1~deb12u2`.

### Phase 13 Backend/API Smoke

Completed for the current pass. Smoke automation exists, runtime-QC event
literal drift is fixed, and current evidence is committed at
`docs/evidence/phase13_smoke_latest.json` for mission
`mission-ac933664-bda8-4acf-b265-10171c2ccdf6`.

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

Completed for tracked security-audit items. The latest production audit passes
23/23 checks; `INF-008` is closed.

### Phase 8 Coverage

Partially closed. New Mission Flow v2 strict-mode tests raise package line
coverage above the older 90% target: the isolated suite passed 81 tests at
91.56% line / 71.69% branch, and the broader related suite passed 170 tests
at 92.43% line / 74.70% branch. The remaining carry-forward is branch
coverage or explicit deferral of the old 85% branch target.

---

## Source Of Truth

- Current app status: this file
- Active work: `docs/CURRENT_TODO.md`
- Handoff: `docs/HANDOFF_CURRENT.md`
- Docs landing page: `docs/README.md`
- Full doc map: `docs/DOCUMENTATION_INDEX.md`
- Historical material: `docs/archive/`
- Qualification evidence: `docs/evidence/`
