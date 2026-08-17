# Implementation Status

Document version: 2026.08.17
Last updated: 2026-08-17
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
- Pod workers with real AST extractors for Python, JavaScript/TypeScript, and Java. Go, Haskell, OCaml, and Julia extractors are named AST but implemented as regex. Pre-flight toolchain checkers exist for all four pods.
- LogicNode schema v2 — descriptive fields promoted to first-class optional properties; `types.in`/`types.out` populated from real AST signatures for Python, Java, and Haskell (see [LOGICNODE_SCHEMA.md](LOGICNODE_SCHEMA.md)). BUILD_NEW missions produce source artifacts; LogicNodes earn their keep on PORT/transform, not as a parallel semantic engine under every new app.
- Refined-IR with a self-describing `projection_method` (`ast_v1` / `templated_v1` / `mixed_v1`). `ast_v1` requires recovered types; otherwise the projection is `templated_v1`.
- Behavioural equivalence verification — Python only (`equivalence_execution.SUPPORTED_LANGUAGES`). BUILD_NEW skips it (no Refined-IR). Opt-in, advisory; see [SUPPORTING_MODULES.md](SUPPORTING_MODULES.md)
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
| Multi-Language AST Extractors | Real AST: Python (`ast`), JS/TS (`esprima`), Java (`javalang`). Go/Haskell/OCaml/Julia files are regex under an AST name. Regex concept catalog still runs for every language. |
| Pod Toolchain Checkers | Pre-flight syntax and compiler checkers live (`toolchains.py`) covering Pods A/B/C/D (`py_compile`, `node --check`, `go vet`, `rustc --parse-only`, `gcc -fsyntax-only`, `javac`, `ghc -fno-code`, `ocamlc -c`) |
| Deployment Handshake Exporters | Downstream deployment exporter engine live (`deploy_exporter.py`), producing gzipped Helm Charts & GitHub Actions workflows via REST endpoints |
| Desktop Electron Build | Electron desktop packaging build passed (`npm run electron:build`), standalone Next.js server bundle assembled, and Docker Desktop/WSL2 daemon preflight active |
| Production Review Audit | Static config/string checks in `scripts/production_review_audit.py`. Useful as a hygiene gate, not as proof the runtime works. |
| Documentation Validation | **100% Passed** (`scripts/validate_documentation.py`) |
| Mission Control Unit Suite | 146/146 Vitest unit tests passed across 26 test files |
| Pytest Backend Suite | **1,868** pytest tests passed, 0 failed, 0 errors |
| Semantic engine (Phases 3–5) | LogicNode v2, real Refined-IR projection, and behavioural equivalence all landed 2026-08-01→02. Verdicts per design area in [ADR_DESIGN_RECONCILIATION_2026-08-01.md](ADR_DESIGN_RECONCILIATION_2026-08-01.md) |
| Sandbox isolation | RQCA runtime QC and behavioural equivalence share **one** hardened Docker invocation (`sandbox_exec.py`); a test fails if either builds its own command line or drops a security flag |
| Stack operations safety | Teardown preserves volumes by default; `start_app.bat` refuses a compose topology that conflicts with what is running |

| Documentation controls | 76 metadata docs, 119 link docs, 17 docstring files, migration guide, and three diagram sets validated cleanly |
| Production audit | Hygiene script, not a live-mission gate. Do not treat a green run as release evidence. |

---

## Remaining Release Gaps

| Area | Status | Notes |
|---|---|---|
| Core Software Engine | **Complete for v1.3 scope** | 11-phase Smelt cycle, 41-agent registry, 6 Redis protocols, AST parsers for all 4 pods, and Deployment Exporters are operational. Refined-IR now carries **real** typed signatures, statement-level op streams, and side-effect-derived purity for AST-backed languages, and labels itself `ast_v1` vs `templated_v1` ([LOGICNODE_SCHEMA.md](LOGICNODE_SCHEMA.md)) |
| Semantic depth | **Partially reinstated; remainder scoped out** | Type recovery is real for Python, Java, and Haskell. Behavioural execution is **Python only**. Other languages produce honestly-empty types and a `templated_v1` projection. Still Superseded or Deferred: the four-pod comprehension model, the LogicNode Registry (Doc 30), binary/LLVM output, and the 0.0001% tolerance. Verdicts in [ADR_DESIGN_RECONCILIATION_2026-08-01.md](ADR_DESIGN_RECONCILIATION_2026-08-01.md) |
| Behavioural equivalence | **Shipped, opt-in, advisory, Python only** | Gated on `MISSION_EQUIVALENCE_PYTHON_EXECUTION_ENABLED` (default `false`). BUILD_NEW skips (no Refined-IR). A vector that merely *ran* is `executed_without_error`, never `passed`. Behavioural results do not flip top-level `passed`. |
| Live mission evidence | **S1-01 captured; matrix still open** | Go CLI `mission-f8a5accf` COMPLETE (`docs/evidence/s1_01_live_generation_go_20260811.json`). Chat-driven PyQt6 `mission-e42fd7e2` COMPLETE. Still owed: a PORT/transform, failure injection, and provider fallback. EDCP is implemented but off (`EVENT_DRIVEN_CONTROL_PLANE_ENABLED=false`) and not live-bus proven. |
| Audit & Quality Standards | **Hygiene green, not a release certificate** | `production_review_audit.py` is a static file/string check. Backend coverage floor 80%, Mission Control Vitest suite exists. Do not cite 23/23 as the release gate. |
| Data plane | **Do not grow** | Postgres, Redis, Qdrant, Milvus, Neo4j, and MinIO already ship. BUILD_NEW does not need more stores. Add a consumer before adding an engine. |
| Orchestrator docker.sock | **Moved to sandbox-runner (2026-08-17)** | Condensed compose mounts `/var/run/docker.sock` on `sandbox-runner` only. Orchestrator calls `SANDBOX_EXECUTOR_URL`. AGENT-41-RQCA still owns the verdict. |
| BUILD_NEW agent honesty (2026-08-16/17) | **Shipped on `main` (PR #460)** | Snake `mission-911a6b3f` showed a working prompt-chain and four role failures. Specialist plans derive from the contract when the LLM emits IR/PEP boilerplate; pod-audit is WARN/unscored without extracted nodes; specified CLI/stdlib games no longer get generic product questions. Follow-up: generated tests run **as** the sandbox command (not after QC, not overwritten by a testdata default `run_command`); syntax-only success is ADVISORY; `while True` / bare `.listen(` no longer force compile-only; cached `started_only` PASS reports are re-assessed. |
| Desktop Packaging Path | **Web path is primary** | `start_app.bat` launches Docker + browser. Electron exists and now uses the Next.js `/api/gateway` proxy (it previously called `:8100` with no API key). Installer signing and uninstall hooks remain open. |


---

## Shipped Defaults

| Setting | Default | Notes |
|---|---|---|
| `MISSION_FLOW_V2_ENABLED` | `true` | Primary runtime path |
| `LANGGRAPH_ENABLED` | `false` | Optional alternative lifecycle engine |
| `LANGGRAPH_CHECKPOINTER` | `none` | Postgres checkpointer requires explicit direct Postgres URL |
| `TESTDATA_AGENT_ENABLED` | `false` | Extra fixtures/deps for richer QC. RQCA no longer depends on this flag to run. |
| `RQCA_AGENT_ENABLED` | `true` | Runtime QC runs on the completion path. Docker missing → honest `DRY_RUN` / `ADVISORY`. |
| `RQCA_ENFORCEMENT_ENABLED` | `true` | Blocks only `qc_verdict == FAIL`. `started_only`, syntax-only, `DRY_RUN`, `SKIPPED`, and `ADVISORY` do not block. Generated tests, when present, are the sandbox command. Turning the agent off while this is on now blocks (skip is not a QC result). Production still fails fast if this is false. |
| `MISSION_SECURITY_COMPLIANCE_ENFORCEMENT_ENABLED` | `true` | Blocking by default — a detected hardcoded secret blocks delivery (`settings.py:92`) |
| `MISSION_EQUIVALENCE_ENFORCEMENT_ENABLED` | `false` | Contract-conformance findings are advisory until pass rates are measured |
| `DEPABS_EXECUTION_ENABLED` | `false` | Dependency absorption execution remains opt-in |
| `LLM_PROVIDER` | `gemini` | Default provider route |
| `GEMINI_MODEL` | `gemini-3.7-flash` | Default model for all agent routes (compose / gateway / vault). |
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
