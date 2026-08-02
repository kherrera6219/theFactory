# Implementation Status

Document version: 2026.08.01
Last updated: 2026-08-01
Status: Canonical
Audience: Operators, developers, maintainers, and auditors

This document is the current-state snapshot for theFactory. When older phase
plans, ADRs, evidence files, or archived documents conflict with this file, this
file wins.

> ### Scope of the completeness claims (corrected 2026-08-01, UPG-12)
>
> Completeness in this document means **complete against the v1.3 mission-pipeline
> scope** — the mission lifecycle, agent registry, protocol bus, data plane,
> security controls, operator UI, and packaging path. It does **not** mean the
> Feb–Mar 2026 design corpus was implemented in full.
>
> Specifically out of scope, by recorded decision rather than omission:
> semantic Refined-IR depth (the projection is templated — see
> [LOGICNODE_SCHEMA.md](LOGICNODE_SCHEMA.md)), behavioural equivalence
> verification (shipped verification is contract conformance), the four-pod
> parallel comprehension model, the LogicNode Registry, and binary/LLVM output.
>
> Each of those carries an Implemented / Superseded / Deferred verdict in
> [ADR_DESIGN_RECONCILIATION_2026-08-01.md](ADR_DESIGN_RECONCILIATION_2026-08-01.md).
> Evidence: [DESIGN_VS_BUILD_AUDIT_2026-08-01.md](DESIGN_VS_BUILD_AUDIT_2026-08-01.md) §4.2–§4.4.

---

## Product Status

theFactory is a local-first AI software factory (Version 1.3.0), **feature-complete
against the v1.3 mission-pipeline scope** defined in
[ADR_DESIGN_RECONCILIATION_2026-08-01.md](ADR_DESIGN_RECONCILIATION_2026-08-01.md).
It is active development, not a production-ready release.

The application currently includes:

- Mission Control Next.js operator UI with Electron desktop packaging
- API gateway with dual-mode auth (API Key + OIDC) and rate limiting
- Orchestrator state engine on MissionFlow v2 (LangGraph ships disabled; see ADR row 13)
- Protocol bus MCP (6-protocol typed Redis message bus with DLQ, 409 replay protection, and 503 backpressure)
- Pod workers with concrete AST extractors for 7 language families & pre-flight toolchain checkers
- Audit worker for verification stream processing
- Dedicated single-agent runtime containers (supporting condensed, dedicated, and full-dedicated topologies)
- Integrated data plane: PostgreSQL, Redis, Qdrant, Milvus, Neo4j, and MinIO
- Prometheus/Grafana/Loki/Jaeger observability stack
- Documentation validation, OpenAPI drift checks, and production review audit suite

---

## Current Proof Points

| Area | Current state |
|---|---|
| Runtime validation | Full-dedicated stack evidence refreshed on 2026-07-25 |
| Rebuild readiness | API gateway and orchestrator readiness passed in current smoke evidence |
| Backend/API mission path | Phase 13 smoke passed |
| Multi-Language AST Extractors | AST structural extractors live across Python (`ast`), JS/TS (`esprima`), Java (`javalang`), Go (`go_ast_extractor`), Haskell (`haskell_ast_extractor`), OCaml (`ocaml_ast_extractor`), and Julia (`julia_ast_extractor`) with zero-false-positive structural extraction and regex fallback |
| Pod Toolchain Checkers | Pre-flight syntax and compiler checkers live (`toolchains.py`) covering Pods A/B/C/D (`py_compile`, `node --check`, `go vet`, `rustc --parse-only`, `gcc -fsyntax-only`, `javac`, `ghc -fno-code`, `ocamlc -c`) |
| Deployment Handshake Exporters | Downstream deployment exporter engine live (`deploy_exporter.py`), producing gzipped Helm Charts & GitHub Actions workflows via REST endpoints |
| Desktop Electron Build | Electron desktop packaging build passed (`npm run electron:build`), standalone Next.js server bundle assembled, and Docker Desktop/WSL2 daemon preflight active |
| Production Review Audit | **23 / 23 Checks Passed** (`scripts/production_review_audit.py`) |
| Documentation Validation | **100% Passed** (`scripts/validate_documentation.py`) |
| Mission Control Unit Suite | 131/131 Vitest unit tests passed across 25 test files |
| Pytest Backend Suite | 1,737 pytest tests passed (100% green) |

| Documentation controls | 76 metadata docs, 119 link docs, 17 docstring files, migration guide, and three diagram sets validated cleanly |
| Production audit | 23/23 audit checks passed; all security and governance requirements closed |

---

## Remaining Release Gaps

| Area | Status | Notes |
|---|---|---|
| Core Software Engine | **Complete for v1.3 scope** | 11-phase Smelt cycle, 41-agent registry, 6 Redis protocols, AST parsers for all 4 pods, and Deployment Exporters are operational. **Refined-IR ships a schema-valid but templated projection**, not a semantic decompilation ([LOGICNODE_SCHEMA.md](LOGICNODE_SCHEMA.md)); real AST-derived projection for AST-backed languages is planned as Phase 4 of the upgrade plan |
| Semantic depth | **Scoped out (recorded decision)** | LogicNodes are 7-field envelopes; equivalence verification is contract conformance, not behavioural; the four-pod comprehension model, LogicNode Registry, and binary/LLVM output are Superseded or Deferred. Verdicts in [ADR_DESIGN_RECONCILIATION_2026-08-01.md](ADR_DESIGN_RECONCILIATION_2026-08-01.md) |
| Audit & Quality Standards | **100% Passed** | 23/23 production audit checks passed, 88.33% backend coverage (floor 80%), 131 UI unit tests green, docs validation clean |
| Desktop Packaging Path | **100% Complete** | Electron build pipeline, embedded standalone server bundle, NSIS installer target, and Docker preflight validation verified |


---

## Shipped Defaults

| Setting | Default | Notes |
|---|---|---|
| `MISSION_FLOW_V2_ENABLED` | `true` | Primary runtime path |
| `LANGGRAPH_ENABLED` | `false` | Optional alternative lifecycle engine |
| `LANGGRAPH_CHECKPOINTER` | `none` | Postgres checkpointer requires explicit direct Postgres URL |
| `TESTDATA_AGENT_ENABLED` | `false` | Runtime QC support is opt-in |
| `RQCA_AGENT_ENABLED` | `false` | Runtime QC support is opt-in |
| `RQCA_ENFORCEMENT_ENABLED` | `true` | Blocking by default — a failed runtime QC check blocks delivery (`settings.py:98`, `:228`). Fails fast in production if disabled |
| `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED` | `true` | Blocking by default — a detected hardcoded secret blocks delivery (`settings.py:92`) |
| `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED` | `false` | Contract-conformance findings are advisory until pass rates are measured |
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

- Current app status: this file (subject to the contested-claims note at the top)
- **Active initiative: `docs/UPGRADE_RECONCILIATION_PLAN_2026-08-01.md` (Phases 1–7)**
- **Design-vs-build gap analysis: `docs/DESIGN_VS_BUILD_AUDIT_2026-08-01.md`**
- Active work: `docs/CURRENT_TODO.md`
- Handoff: `docs/HANDOFF_CURRENT.md`
- Docs landing page: `docs/README.md`
- Full doc map: `docs/DOCUMENTATION_INDEX.md`
- Historical material: `docs/archive/`
- Qualification evidence: `docs/evidence/`
