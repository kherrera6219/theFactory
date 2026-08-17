# AGENTS.md — theFactory / Holy Grail Refinery (HGR)

> Read this file fully before touching any file. When docs and code disagree, code is truth.
> Last validated: 2026-08-17 after live PORT-through-SOW (`mission-dc0c8c4e` COMPLETE) and failing-QC-blocks-COMPLETE (`mission-8db1af71` VERIFIED). RQCA docker probe uses `SANDBOX_EXECUTOR_URL`.

---

## 0. CURRENT WORK — read this before anything else

Active initiative as of **2026-08-01**. Read `docs/CURRENT_TODO.md` and
`docs/HANDOFF_CURRENT.md` first — they carry session state and point here.
Two documents are canonical for all forward work:

| Document | What it is |
|---|---|
| `docs/ADR_DESIGN_RECONCILIATION_2026-08-01.md` | **The governing verdict document.** One Implemented / Superseded / Deferred verdict per design area. **It outranks the numbered design corpus.** A Superseded verdict is a closed decision — reopening one requires an ADR amendment, not a plan edit. |
| `docs/UPGRADE_RECONCILIATION_PLAN_2026-08-01.md` | The ordered execution plan, **Phases 1–7**. Start at its §0 "Cold start" — it tells you exactly what to read, in what order. |
| `docs/DESIGN_VS_BUILD_AUDIT_2026-08-01.md` | The read-only audit behind it: 143 design documents vs live source, with file/line evidence. |
| `docs/DESIGN_TRACEABILITY.md` | Design document 01–64 → status → implementing module → evidence. Answers "where is Doc N implemented?" without re-reading the corpus. |

**Progress as of 2026-08-17:** Phases 1–5 and 7 **done**; Phase 2 **done
including UPG-20** (`docs/evidence/s1_01_live_generation_go_20260811.json`).
Phase 6 (EDCP-02a) is implemented but off and not live-bus proven. Honesty
gates, Gemini 3.7 Flash, and tests-as-QC are on `main` (PR #460). The PM
SOW factory (P0–P4) is in code: Chat ZIP / repo handoff, file-tree
delivery, quoted-vs-actual cost, change orders, and `sandbox-runner`
owning `docker.sock`. **Next is live proof of that path, then a
one-mission EDCP live-bus run** — see `docs/WORK_QUEUE.md`.

> **Executing generated code goes through `orchestrator/sandbox_exec.py` and
> nowhere else.** In compose the orchestrator POSTs to `SANDBOX_EXECUTOR_URL`
> (`sandbox-runner`); only that service mounts `docker.sock` and runs
> `docker`. RQCA and behavioural equivalence still share one hardened
> invocation. Do not add a second `docker run` command line, and do not relax
> any flag in `SANDBOX_SECURITY_FLAGS` — a test fails if you do.

**This plan's own premises do not always survive contact with the code — six
have failed validation so far.** Before assuming any `UPG-*` item was skipped or
done as written, read the corrections recorded in the ADR's "Corrections to the
audit and plan" section, `docs/PROTOCOL_ENVELOPES.md` §4, and the per-phase
status blocks in the plan itself. Verify against live source before trusting a
plan statement — rule 1 below is not a formality here.

**Next action:**

- Rebuild the stack so `sandbox-runner` and Chat ZIP are live, then prove
  Chat SOW + ZIP PORT/update through Accept SOW (`docs/WORK_QUEUE.md` item 5).
- Then **Phase 6 live-bus**: `EVENT_DRIVEN_CONTROL_PLANE_ENABLED=true` on
  **one** mission. EDCP-02a is already in code. Before exercising it, read
  `docs/PROTOCOL_ENVELOPES.md` §4: the two transports join by **prefix
  parse, never equality**, and a consumer that queries
  `correlation_id == mission_id` finds nothing and fails silently.

Work item IDs are `UPG-<phase><item>` — `UPG-2x` is Phase 2, `UPG-3x` is
Phase 3, and so on. Phase 6 uses the `EDCP-*` IDs from
`docs/EDCP_PHASE_PLAN.md` instead.

**Three decisions are settled. Do not reopen them, and refuse work that
contradicts them:**

| # | Decision | Chosen |
|---|---|---|
| D1 | Semantic engine | **Pragmatic middle** — enrich LogicNodes additively, make Refined-IR extraction real where AST support already exists, build execution-based equivalence for a language subset. **Keep single-specialist routing. No 4-pod fan-out.** |
| D2 | Binary synthesis / LLVM | **Formally killed.** Never implemented. Note: this retires binary *synthesis*, NOT `toolchains.py` syntax *validation*, which stays. |
| D3 | Protocol Bus | **Commit to EDCP** — make it load-bearing, starting with a Delta consumer that can gate a mission (new EDCP-02a in `docs/EDCP_PHASE_PLAN.md`). |

**Explicit non-goals** are listed in the upgrade plan §11 (four-pod fan-out, LLVM,
the 0.0001% tolerance claim, the design Doc 30 LogicNode Registry, per-agent LLM
provider keys, Agent Runtime Split, Semantic Bus). **§14 of the same plan lists
what must not be weakened.**

> **Do not treat the numbered design documents (01–64) as current specification.**
> They are the Feb–Mar 2026 design phase, archived at
> `docs/archive/2026-03-29/legacy-workspace/root-legacy-documentation/` (see the
> README there) and **superseded in part as of 2026-08-01** — per-document status
> is in `docs/DESIGN_TRACEABILITY.md`. `HGR_Gap_Report.md`-style material is stale
> in its "what's missing" sections; six of its claims were verified closed.

---

## 1. Project Identity

**theFactory** is the Holy Grail Refinery (HGR): a multi-agent AI software manufacturing system.
It accepts a natural-language mission and delivers working software through a fully automated pipeline.

- **Stack**: Python (76%), TypeScript (20%), Docker monorepo
- **Core model (as designed)**: 19 language specialists → 4 paradigm pods → 1 unified output (LogicNodes / Refined-IR)
- **Core model (as built — code is truth)**: a mission resolves **one** pod manager and **one** specialist from `requested_target_language` (`mission_flow_v2/phases_build.py:328+`) and produces **source artifacts**, not a binary. Pods are routing metadata; there is no parallel four-pod fan-out and no cross-language fusion. See `docs/DESIGN_VS_BUILD_AUDIT_2026-08-01.md` §4.1. Decision D1 keeps it this way.
- **Smelt Cycle (MVP)**: INTAKE → FETCH → SMELT → GATING → FUSION → SQUEEZE → DELIVERY
- **Six Redis Protocols**: Alpha (α) Directive · Beta (β) Production · Delta (δ) Audit · Sigma (σ) Knowledge · Omega (ω) User · Rho (ρ) Traffic

## 2. Runtime Model — What Is Actually Deployed

**Default topology**: Condensed. NOT the full isolated 41-agent model.

| Agent class | Shipped state |
|---|---|
| PM Agent, CEO/Grand Manager | Real processes |
| Pod workers (A/B/C/D) | Real **shared** workers — one container per pod family, not per-language |
| Language specialists (e.g. Go, Haskell, OCaml) | Real pod assignments inside shared pod workers — **not** virtual personas. Go, Haskell, and OCaml now have concrete SpecialistAgent subclasses (GoAgent, HaskellAgent, OcamlAgent) — no longer falling back to BaseAgent. |
| Interface / Executive / Support ring | Synthesized heartbeats generated by orchestrator (`main.py:664–762`) |

The 41-agent registry exists in code. The deployed default is condensed.
The `full-dedicated-agents` Compose profile provides per-language isolated containers.

> Never assume all 41 agents are real isolated processes. Check `AGENT_AUTOFILL_NON_POD_HEARTBEATS`
> to know whether non-pod agent heartbeats are synthesized.

## 3. Lifecycle Engine

| Engine | Status | Gate |
|---|---|---|
| Mission Flow v2 | **DEFAULT** | `MISSION_FLOW_V2_ENABLED=true` (default) |
| LangGraph | Optional, not default | `LANGGRAPH_ENABLED=false` (default) |
| Legacy v1.1 | Compatibility shim only | Used when v2 disabled — not a supported production path |

Engine selection is in `services/orchestrator/orchestrator/runtime.py:539`.
All three paths emit identical lifecycle events via `emit_state_event()`.

## 4. Extraction Engine

The language-analysis layer uses **regex-based** pattern detection for 20 language keys.

**Exception**: Three languages now have AST-backed extractors alongside regex:
- **Python** (`ast_extractor.py`) — enable via `PYTHON_AST_EXTRACTOR_ENABLED=true`; uses `ast` module for structural accuracy; regex still runs for concept detection; falls back on syntax errors. **Default: true in docker-compose** (`${PYTHON_AST_EXTRACTOR_ENABLED:-true}`) across all pod workers; pod-worker Python code fallback is `false` if env var is absent outside compose.
- **JavaScript / TypeScript** (`js_ast_extractor.py`) — enable via `JS_AST_EXTRACTOR_ENABLED=true`; uses `esprima`; strips TS syntax before parsing; preserves regex concept detection and fallback. *(implemented 2026-05-17)* **Default: true in docker-compose** (`${JS_AST_EXTRACTOR_ENABLED:-true}`) and `.env.example`.
- **Java** (`java_ast_extractor.py`) — enable via `JAVA_AST_EXTRACTOR_ENABLED=true`; uses `javalang`; extracts packages, imports, classes, constructors, methods, annotations; preserves regex concept detection and fallback. *(implemented 2026-05-17)* **Default: true in docker-compose** (`${JAVA_AST_EXTRACTOR_ENABLED:-true}`) and `.env.example`.

Language routing:
- **Pod A — Dynamic**: Python, JavaScript, TypeScript, Ruby, PHP
- **Pod B — Systems**: C, C++, Rust, Go, Zig
- **Pod C — Enterprise**: Java, C#, Scala, Kotlin
- **Pod D — Mathematical & Functional**: R, MATLAB, Julia, Mathematica, Haskell, OCaml


### 5. Professional Grounding (Certified Experts)
As of v1.1.0, all agents are grounded as **Certified Experts** in their respective domains.
- **Systems (Pod B)**: Enforce MISRA C:2012, buffer-safety, and RAII rules.
- **Web (Pod A)**: Enforce PEP 8/604, ECMAScript 2024, and OWASP safety.
- **Enterprise (Pod C)**: Enforce SOLID patterns, JVM hygiene, and .NET async correctness.
- **Admin Mode**: Authentication is now implicitly tied to the host OS; full administrative capabilities are enabled by default for zero-friction local usage.
- **Multimodal Assets**: The PM Agent chat intake accepts all document formats (e.g., PDF) and image types (e.g., diagrams), converting them to Base64 Data URLs that are parsed by the provider layer (`providers.py`) and sent natively to multimodal LLMs (`inlineData` for Gemini, `image_url` for OpenAI).

## 6. Known Open Gaps

| Gap | Status |
|---|---|
| DLQ on intake stream | ✅ Fixed — `_write_intake_dlq()` in `orchestrator/runtime.py:394` |
| MCP_API_KEY auto-gen instability | ✅ Fixed — production hard-fails; dev warns loudly (`mcp_server.py:32`) |
| Silent AUTH_MODE fallback | ✅ Fixed — invalid `AUTH_MODE` raises in every environment; no fallback to `api_key` |
| Cert path mismatch (.env.example vs docker-compose) | ✅ Fixed — `.env.example` now explains both paths with inline comments |
| GO/HASKELL/OCAML fall back to BaseAgent | ✅ Fixed — concrete SpecialistAgent subclasses implemented (#187) |
| MCP replay detection not wired; except/pass on Redis errors | ✅ Fixed — 409 on replay, 503 on Redis failure, all channels checked (#188) |
| Divergent envelope schemas | ⚠️ **Partially fixed.** The Redis *state-event* envelope is unified and `jsonschema.validate()`d in the orchestrator (#189). But two envelope formats remain in production and disagree: `schemas/event.envelope.schema.json` allows `priority` ∈ `NORMAL\|HIGH`, while the bus `/send` body allows `low\|normal\|high\|critical`. Latent (nothing routes on priority yet). Tracked as UPG-22 (upgrade plan Phase 2). |
| Semantic bus routing misleadingly named | ✅ Fixed — renamed to protocol-bus-mcp throughout (#190) |
| Generated artifacts committed to VCS | ✅ Fixed — removed + `.gitignore`d (#191) |
| runtime.py coverage floor 60% | ✅ Fixed — raised to 80%, actual coverage 100% line (#192) |
| `any` types in api-client.ts; gateway 200-on-error | ✅ Fixed — OpenAPI-generated types, real HTTP status codes (#193) |
| agent_personas.py parallel dict drift | ✅ Fixed — unified `AgentPersona` dataclass per agent (#194) |
| Knowledge Lake write/read split (IS-Agent → PostgreSQL, query layer → Qdrant; zero query call sites) | ✅ Fixed (Phase 2) — `knowledge_lake.py` reads PostgreSQL (`storage.list_knowledge`) as the single source of truth; `get_language_context` injected into specialist codegen (`phases_build.py`); `is_stocked` verifies write-back in FETCH; `embed_text` adds gemini/openai/none providers with Qdrant mirror for semantic search |

> runtime.py coverage floor raised to 80% (actual: 100% line / 99% branch) via 12 new branch-coverage tests (#192).

## 7. Definition of Done (per task)

- [ ] No existing tests broken (`make test` + `make test-ui`)
- [ ] Docs updated to match code changes (no new drift)
- [ ] Extractor changes include fixture comparison (old vs new output)
- [ ] Orchestrator changes do not alter external API contract without explicit approval
- [ ] Runtime topology assertions in comments/docstrings remain accurate
- [ ] Security controls (replay detection, deduplication, circuit breakers) not regressed
- [ ] `AGENTS.md` updated if architecture changes

## 8. File Sensitivity

| Path | Sensitivity | Notes |
|---|---|---|
| `services/orchestrator/orchestrator/storage_*.py` | **Critical** | Storage split complete (2026-05-17): `storage.py` is now a 135-line re-export façade; domain logic is in `storage_core.py`, `storage_missions.py`, `storage_pods.py`, `storage_logicnodes.py`, `storage_artifacts.py`, `storage_agents.py`. Changes to any storage module affect all services. |
| `services/orchestrator/orchestrator/mission_flow_v2/` | **Critical** | Primary runtime path. **It is a package, not a single file** — `base.py`, `lifecycle.py`, `transitions.py`, `phases_intake.py`, `phases_build.py`, `phases_runtime.py`, `phases_delivery.py`. (`mission_flow.py` alongside it is a separate module holding the pod/specialist language maps.) |
| `services/orchestrator/orchestrator/main.py` | **High** | Routes + lifespan tasks + approvals. Heartbeat synthesis extracted to `heartbeat_service.py`; knowledge refresh loop added at startup. |
| `services/pod-worker/pod_worker/extractors/` | **High** | Core semantic engine. Fixture tests required for changes. |
| `shared/schemas/` | **High** | Schema changes break all services. Coordinate. |
| `services/api-gateway/` | **Medium** | Auth modes, key isolation, rate limiting |
| `services/protocol-bus-mcp/` | **Medium** | Protocol Bus MCP (`:8102`) — protocol routing. Do not rename streams without updating all consumers. |
| `apps/mission-control/` | **Medium** | UI must match actual backend behavior |

---

## Repository Structure & Module Organization
- `apps/mission-control`: Next.js operator UI (routes under `app/`, unit tests, and Playwright e2e).
- `services/`: backend services (`api-gateway`, `orchestrator`, `pod-worker`, `audit-worker`, `protocol-bus-mcp`, `dashboard`).
- `scripts/`: operational tooling (audit, perf, reliability, backup/DR, debug sweep, OpenAPI export).
- `tests/`: Python tests split by domain (`tests/services`, `tests/scripts`).
- `deploy/`: Docker Compose stacks and monitoring config.
- `docs/`: canonical plans, audits, runbooks, and roadmap status.

## Runtime Model

### Topology modes

| Mode | Description | Compose profile |
|---|---|---|
| `condensed` | Shared pod-worker containers + synthesized heartbeats for non-pod agents (default) | _(default)_ |
| `dedicated` | One container per pod manager | `dedicated-agents` |
| `full-dedicated` | One container per language specialist | `full-dedicated-agents` |

Set via `TOPOLOGY_MODE` env var (default: `condensed`). The `runtime_class` field on each `AgentDefinition` reflects this: `shared_worker` for specialist/pod_manager/pod_audit categories, `synthesized_heartbeat` for interface/executive/support.

### Lifecycle engines

| Engine | Flag | Notes |
|---|---|---|
| `MissionFlowV2Engine` | `MISSION_FLOW_V2_ENABLED=true` (default) | 11-phase granular state machine |
| `LangGraphEngine` | `LANGGRAPH_ENABLED=true` + v2 disabled | EXPERIMENTAL — falls back to legacy if dep missing |
| `LegacyV1Engine` | both disabled | COMPATIBILITY SHIM — coarse 3-transition v1.1 |

Factory: `get_lifecycle_engine(settings)` in `orchestrator/lifecycle_interface.py`.

### Extraction engine

The pod-worker extracts concepts from source code using regex by default. Three languages also have full AST-backed extractors (all production-ready, feature-flagged):
- **Python** — `PYTHON_AST_EXTRACTOR_ENABLED=true`; uses `ast` module; zero false positives for structural fields; regex still runs for concept detection; falls back on syntax errors. **Default: true in docker-compose** (`${PYTHON_AST_EXTRACTOR_ENABLED:-true}`) across all pod workers; pod-worker Python code fallback is `false` if env var is absent outside compose.
- **JavaScript/TypeScript** — `JS_AST_EXTRACTOR_ENABLED=true`; uses `esprima`; strips TS syntax before parsing; preserves regex fallback. *(implemented 2026-05-17)*
- **Java** — `JAVA_AST_EXTRACTOR_ENABLED=true`; uses `javalang`; extracts packages, imports, classes, constructors, methods, annotations; preserves regex fallback. *(implemented 2026-05-17)*

## Build, Test, and Development Commands
- `make up` / `make down`: start/stop the full local Docker stack.
- `make tls-certs`: generate local PostgreSQL and Redis TLS certs before first stack startup.
- `make lint`: run Ruff checks on `services`, `tests`, and `scripts`.
- `make test`: run backend pytest with coverage gates.
- `make test-ui`: run Mission Control TypeScript lint + Vitest unit tests.
- `make test-ui-e2e`: run Mission Control Playwright e2e suite.
- `make validate`: full gate — lint + schema validation + pytest + npm lint/test.
- `make audit`: run production checklist audit script.
- `make sweep`: run schema/tests/health/readiness/metrics debug sweep.
- UI local dev: `cd apps/mission-control && npm run dev`.

## Coding Style & Naming Conventions
- Python: 4-space indentation, `snake_case` for functions/files, `PascalCase` for classes.
- TypeScript/React: follow existing 2-space style, `PascalCase` components, `camelCase` helpers/hooks.
- Keep route files consistent with Next App Router conventions (`page.tsx`, `layout.tsx`, `route.ts`).
- Lint rules: Ruff (`E,F,I,B`) with max line length `100`; Mission Control uses strict TypeScript (`tsc --noEmit`).

## Testing Guidelines
- Frameworks: `pytest` (backend/scripts), `vitest` (UI unit), `playwright` (UI e2e).
- Naming: Python `test_*.py`; UI unit `*.test.ts`; e2e `*.spec.ts`.
- Coverage policy: backend **line ≥80%**, **branch ≥70%**, mixed ≥80%, plus
  per-module floors (sandbox/SOW/PORT/RQCA/toolchains and the original
  protocol/runtime files) via `scripts/check_coverage_thresholds.py`.
  Mission Control: Vitest coverage on `app/lib/**` (`npm run test:coverage`).
  A red suite invalidates the coverage number.
- Before merge: `make lint`, `make test`, `make test-ui`, `make test-ui-e2e`, `make audit`.

## Commit & Pull Request Guidelines
- Follow observed history style: imperative, scoped subjects like `phase11: ...` or `chore: ...`.
- Keep commits focused to one phase/change set and include matching doc updates in `docs/` when behaviour changes.
- PRs should include: problem/solution summary, linked task/issue, validation commands run, and UI screenshots for frontend changes.

## Security & Configuration Tips
- Start from `.env.example`; never commit secrets or real API keys.
- PostgreSQL and Redis private keys are generated locally with `make tls-certs` and must never be committed.
  - Docker containers use `/run/secrets/` or volume mounts for certs. Local dev uses `deploy/.local/`.
- Use Mission Control vault endpoints for local key handling (`/api/vault`, `/api/vault/test`).
- Avoid committing generated artifacts unless intentionally required (e.g. `coverage.xml`, `tsconfig.tsbuildinfo`).

## High-sensitivity files

| File | Risk | Notes |
|---|---|---|
| `services/orchestrator/orchestrator/storage_*.py` | High | Storage split done (2026-05-17) — `storage.py` is now a 135-line re-export façade; 6 domain modules hold the logic. High blast radius: changes to any module affect all services. |
| `services/orchestrator/orchestrator/mission_flow_v2.py` | High | 3004 lines — primary runtime path. Intelligence layer completions (Sprint 2) go here. |
| `services/orchestrator/orchestrator/main.py` | High | ~926 lines. Heartbeat synthesis extracted to `heartbeat_service.py`; knowledge_lake_refresh_loop added (Sprint 2 item complete). |
| `services/orchestrator/orchestrator/runtime.py` | Medium | Delegates engine selection to `lifecycle_interface.py` via `get_lifecycle_engine()` factory. |
| `services/orchestrator/orchestrator/agent_registry.py` | Medium | Source of truth for all 41 agent definitions |

See `docs/codex/DEFINITION_OF_DONE.md` and `docs/codex/REVIEW_CHECKLIST.md` for change gates.
