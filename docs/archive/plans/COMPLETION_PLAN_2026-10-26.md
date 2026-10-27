# 100% Completion Execution Plan — `theFactory` (Code-Validated)

Document version: 1.0
Last updated: 2026-10-26
Status: Canonical
Audience: Engineering, Operations

> **Governing Constraint (`AGENTS.md` §0):**
> This plan strictly honors Decisions **D1** (single-specialist routing, pragmatic middle semantic engine, no 4-pod fan-out), **D2** (no LLVM / binary synthesis), and **D3** (commit to EDCP). Every file, function, SQL query, and UI component below has been validated directly against the live codebase.

---

## 0. Plan-vs-Code Validation Findings (Corrected Against Live Source)

Validating the plan against the live codebase across the **Backend**, **AI Agents**, **Internal Database System**, and **Frontend UX/UI** exposed **8 concrete findings** that are addressed in Phases 1–6:

1. **Knowledge Lake 10-Row Truncation Bug (`services/orchestrator/orchestrator/knowledge_lake.py:191`):**
   - `get_language_context()` calls `list_knowledge(settings, _KNOWLEDGE_LAKE_ID, limit=10)` and then filters in Python for `docs.<language>.bootstrap`. That worked when `_BOOTSTRAP_DOCS` had only 4 languages (`python`, `javascript`, `typescript`, `java`), but expanding `_BOOTSTRAP_DOCS` to all 20 language keys causes `limit=10` to silently drop 10 of the 20 languages! We must raise the limit in `get_language_context` (`limit=100`) alongside expanding `_BOOTSTRAP_DOCS` in `services/orchestrator/orchestrator/is_agent.py`.
2. **Extractor `projection_method` Contract (`services/pod-worker/pod_worker/language_extractor.py:787-956`, `services/pod-worker/pod_worker/refined_ir.py:286-287`):**
   - `tests/services/test_refined_ir_projection_unit.py:113-124` (`test_regex_only_language_still_reports_templated_v1`) tests `language="sql"` (which resolves to the base `LanguageExtractor`) and asserts `module.projection_method == "templated_v1"`. Therefore, the base `LanguageExtractor` must stay signature-free while concrete language extractors recover `arg_types`, `return_type`, `purity`, `side_effects`, and `ops`.
3. **AI Agent Factory Missing `"typescript"` Mapping (`services/orchestrator/orchestrator/agent_base.py:802-872`):**
   - `_SPECIALIST_BY_LANGUAGE` maps `"javascript": JavaScriptAgent` but **omits `"typescript"`**. Because `AGENT-07-TS-JS` declares `specialties=("typescript", "javascript")`, both `make_agent("AGENT-07-TS-JS")` (which checks `definition.specialties[0]`) and `make_specialist_for_language("typescript")` fall back to the bare `SpecialistAgent` base class (`language_key=""`) instead of `JavaScriptAgent`!
4. **AI Agent `SpecialistAgent._extract_logicnodes` & `SupportAgent` Stubs (`services/orchestrator/orchestrator/agent_base.py:399-684`):**
   - `SpecialistAgent._extract_logicnodes` uses a 3-line regex (`def|function|fn|func`) that misses functional/mathematical languages (`:=`, `<- function`, `let rec`, `::`, `classdef`) and omits Certified Expert persona metadata from `agent_personas.py`. Meanwhile, all 12 Support Ring agents (`BROKER`, `ACCOUNTANT`, `SECURITY`, `IS`, `VC`, `COMPLIANCE`, `HW`, `TESTER`, `DEPLOY`, `DEPABS`, `TESTDATA`, `RQCA`) share a single generic `SupportAgent` stub without role-specific artifact schemas or validation rules.
5. **Specialist Self-Repair Lifecycle Stage (`services/orchestrator/orchestrator/mission_flow_v2/phases_runtime.py:366-655`, `services/orchestrator/orchestrator/llm_delegation/generators.py:318`, `services/orchestrator/orchestrator/llm_delegation/prompts.py:430`):**
   - Specialist codegen lives in `llm_delegation/generators.py` (`generate_code_from_contract`) and `llm_delegation/prompts.py` (`_build_codegen_prompt`), and Runtime QC runs during the `VERIFIED -> COMPLETE` gate inside `_prepare_runtime_qc` (`phases_runtime.py`).
6. **Database Lost-Update Race on `missions.metadata_json` (`services/orchestrator/orchestrator/mission_flow_v2/phases_build.py:970-1014`, `services/orchestrator/orchestrator/storage_missions.py:347-365`):**
   - `_produce_pod_group_standard` emits `_send_delta_audit_verdict` at line 970 *before* calling `_persist_metadata` at line 1004. When `_handle_delta_audit_verdict` (`main.py:523-574`) writes `metadata["delta_audit_gate"]` to Postgres concurrently, line 1004's stale local `metadata` dict overwrites and erases `delta_audit_gate`.
7. **Frontend `DatabasesPage` No-Op Retry & Missing Internal DB Diagnostics (`apps/mission-control/app/(shell)/databases/page.tsx:265-275`):**
   - The `"Retry Connection"` button on `DatabasesPage` only runs `setTimeout(r, 400)` without calling `load()`, and the page does not surface internal PostgreSQL table row counts, connection pool metrics, schema migration version, or an operator trigger for the existing `POST /v1/maintenance/prune-audit` retention endpoint.
8. **Frontend `LogicNodesPage` & `RuntimeQcPanel` Schema Drift (`apps/mission-control/app/(shell)/logicnodes/page.tsx:14-31`, `apps/mission-control/app/(shell)/missions/detail/panels/intelligence/RuntimeQcPanel.tsx`):**
   - `LogicNodesPage` reads `node.intent`/`node.domain`/`node.confidence` only at the top level of `node.node`, ignoring v2 `node.node.payload` and hiding `types.in`, `types.out`, `purity`, `side_effects`, and `op_stream`. `RuntimeQcPanel.tsx` omits `stderr_preview`, `exit_code`, self-repair status, and the EDCP `delta_audit_gate` verdict.

---

## Phase 1: 20-Language Knowledge Lake Parity (`is_agent.py` & `knowledge_lake.py`)

**Goal:** Expand the Knowledge Lake bootstrap seed from 4 languages (`python`, `javascript`, `typescript`, `java`) to all 20 language keys across the 19 specialists and fix the 10-row query truncation in `knowledge_lake.py`.

### Changes
1. **`services/orchestrator/orchestrator/is_agent.py`**:
   - Add Certified-Expert grounding entries (idioms, type-safety rules, memory/concurrency invariants, testing conventions, and security pitfalls) to `_BOOTSTRAP_DOCS` for all **16 missing language keys**: `ruby`, `php`, `c`, `cpp`, `rust`, `go`, `zig`, `csharp`, `scala`, `kotlin`, `r`, `matlab`, `julia`, `mathematica`, `haskell`, `ocaml`.
   - Expand `detect_required_languages()` in `is_agent.py` to recognize keywords and file extensions for all 20 language keys (preserving `"python"` fallback for unsupported languages like `"cobol"`).
2. **`services/orchestrator/orchestrator/knowledge_lake.py`**:
   - Update `get_language_context()` and `is_stocked()` to query `limit=100` (up from `10` and `50`) so all 20 bootstrap docs + library docs are retrievable.
3. **`tests/services/test_is_agent_fetch_unit.py`**:
   - Add unit tests verifying all 20 language keys in `_BOOTSTRAP_DOCS` stock and retrieve non-empty context via `get_language_context()`.

---

## Phase 2: Structural & Refined-IR Enrichment Across Extractors (`pod-worker`)

**Goal:** Upgrade the structural extractors so `LogicNode` and `RefinedIRFunction` carry real `types.in`, `types.out`, `purity`, `side_effects`, and `ops` across the language fleet while keeping the base `LanguageExtractor` (`generic` / `sql`) untouched.

### Changes
1. **`services/pod-worker/pod_worker/js_ast_extractor.py` & `java_ast_extractor.py`**:
   - Recover TypeScript parameter/return type annotations, statement opcodes (`RETURN`, `IF`, `FOR`, `WHILE`, `TRY`, `AWAIT`, `CALL`, `ASSIGN`), `purity` (`PURE`/`IMPURE`), and `side_effects` in `js_ast_extractor.py` and `java_ast_extractor.py`, wiring them into `JavaScriptAstExtractor` and `JavaAstExtractor` in `language_extractor.py`.
2. **`services/pod-worker/pod_worker/go_ast_extractor.py`, `ocaml_ast_extractor.py`, `julia_ast_extractor.py`, & `language_extractor.py`**:
   - Recover declared parameter/return types, `purity`, `side_effects`, and `ops` in `GoAstExtractor`, `OCamlAstExtractor`, `JuliaAstExtractor`, `HaskellAstExtractor`, and the typed language subclasses (`RustExtractor`, `CExtractor`, `CppExtractor`, `ZigExtractor`, `CSharpExtractor`, `ScalaExtractor`, `KotlinExtractor`, `PhpExtractor`).
3. **`services/pod-worker/pod_worker/refined_ir.py`**:
   - Extend `_TYPE_SAMPLES` and `_sample_value_for_type()` to normalize static types across Rust, Go, C/C++/Zig, C#/Scala/Kotlin, and Julia/Haskell/OCaml into concrete equivalence test vectors.
4. **`tests/services/test_refined_ir_projection_unit.py`**:
   - Add multi-language `ast_v1` projection and equivalence-vector tests while keeping `test_regex_only_language_still_reports_templated_v1` passing.

---

## Phase 3: AI Agent Hierarchy Completion & Bounded Runtime QC Self-Repair

**Goal:** Complete the 41-agent class hierarchy in `agent_base.py` (fixing the `"typescript"` specialist lookup bug, enriching all 19 specialist agents with Certified Expert persona grounding, and adding role-specific execution/validation for all 12 Support Ring agents) and wire a bounded 1-attempt file-level self-repair loop into `_prepare_runtime_qc`.

### Changes
1. **`services/orchestrator/orchestrator/agent_base.py`**:
   - Register `"typescript": JavaScriptAgent` in `_SPECIALIST_BY_LANGUAGE` so `make_agent("AGENT-07-TS-JS")` and `make_specialist_for_language("typescript")` resolve to `JavaScriptAgent`.
   - Enrich `SpecialistAgent` (`execute`, `capabilities`, and `_extract_logicnodes`) with language-specific patterns for all 20 language keys and Certified Expert persona metadata (`get_language_persona` from `agent_personas.py`).
   - Upgrade `SupportAgent` with role-specific artifact schemas and validation checks keyed by `short_code` (`BROKER`, `ACCOUNTANT`, `SECURITY`, `IS`, `VC`, `COMPLIANCE`, `HW`, `TESTER`, `DEPLOY`, `DEPABS`, `TESTDATA`, `RQCA`).
2. **`services/orchestrator/orchestrator/llm_delegation/prompts.py` & `services/orchestrator/orchestrator/mission_flow_v2/phases_runtime.py`**:
   - Extend `_build_codegen_prompt()` (`prompts.py`) to inject `runtime_qc_repair_context` (`stderr_preview`, `stdout_preview`, failing files, and current source bundle) when present.
   - In `_prepare_runtime_qc()` (`phases_runtime.py`), when the initial `run_runtime_qc` call returns `verdict == "FAIL"` and `not metadata.get("runtime_qc_repair_attempted")`, invoke a bounded 1-attempt specialist repair via `_pkg().generate_code_from_contract(...)`, merge patched `## FILE` sections into `generated_output`, re-run `run_runtime_qc`, and append a `MISSION_RUNTIME_QC_REPAIRED` chain event.
3. **`tests/services/test_agent_base_unit.py` & `tests/services/test_rqca_unit.py`**:
   - Add unit tests covering `make_agent("AGENT-07-TS-JS")`, `make_specialist_for_language("typescript")`, all 12 Support Ring role validations, and the bounded 1-attempt Runtime QC self-repair pass.

---

## Phase 4: Internal Application Database System & EDCP Delta Gate Hardening

**Goal:** Eliminate the PostgreSQL `metadata_json` lost-update race on `delta_audit_gate`, add expression indexes for JSONB queries in a new `V011` schema migration, and expose live PostgreSQL storage/pool/migration diagnostics through the operations API.

### Changes
1. **`services/orchestrator/orchestrator/storage_missions.py` & `phases_build.py`**:
   - Update `UPDATE_MISSION_METADATA_SQL` in `storage_missions.py` so that an existing `metadata_json -> 'delta_audit_gate'` key in PostgreSQL is atomically preserved when a concurrent lifecycle writer updates `metadata_json` with a dict that lacks `delta_audit_gate`.
   - Reorder `_produce_pod_group_standard()` in `phases_build.py` so `_persist_metadata` commits to Postgres *before* `_send_delta_audit_verdict` publishes to the Protocol Bus.
2. **`services/orchestrator/orchestrator/migrations/V011_database_performance_indexes.sql`**:
   - Add expression/composite indexes for high-frequency JSONB lookups:
     - `idx_mission_knowledge_language` on `mission_knowledge ((content_json->>'language'))`
     - `idx_mission_logicnodes_domain` on `mission_logicnodes ((node_json->>'domain'))`
     - `idx_missions_project_state` on `missions (project_id, state, updated_at DESC)`
3. **`services/orchestrator/orchestrator/storage_core.py`, `storage.py`, & `routes/operations.py`**:
   - Add `get_database_diagnostics(settings)` in `storage_core.py` returning connection pool statistics (`min_size`, `max_size`, `pool_available`), applied schema migration version/count from `schema_migrations`, per-table row counts across core tables (`missions`, `mission_logicnodes`, `mission_knowledge`, `mission_build_artifacts`, `mission_runtime_qc`, `agent_action_events`, `llm_usage_events`, `projects`), and stocked Knowledge Lake language count.
   - Include `database_diagnostics` in `GET /internal/operations/summary` (`routes/operations.py`) and export updated OpenAPI types if needed.

---

## Phase 5: Frontend UX/UI Completion (`apps/mission-control`)

**Goal:** Complete the Mission Control operator UI so every backend subsystem (Internal Database Diagnostics & Audit Retention, Enriched LogicNodes & Refined-IR, Runtime QC Self-Repair, and EDCP Delta Gate) is accurately rendered and actionable.

### Changes
1. **`apps/mission-control/app/(shell)/databases/page.tsx`**:
   - Extract `load` into a `useCallback` and wire the `"Retry Connection"` button to actually call `void load()`.
   - Add an **Internal PostgreSQL Storage & Schema Diagnostics** panel displaying live table row counts, connection pool sizing, schema migration version, Knowledge Lake stocked languages, and a **"Prune Expired Audit Logs"** button wired to `pruneAuditTables()` (`POST /v1/maintenance/prune-audit`).
2. **`apps/mission-control/app/(shell)/logicnodes/page.tsx`**:
   - Upgrade `extractNodeSummary()` and the node cards to read both top-level fields and nested `node.payload` / `node.types` fields, displaying `purity` (`PURE` / `IMPURE` / `UNKNOWN`), `types.in -> types.out` signatures, `side_effects`, `op_stream` opcodes, and AST vs. templated extraction badges.
3. **`apps/mission-control/app/(shell)/missions/detail/panels/intelligence/RuntimeQcPanel.tsx` & `apps/mission-control/app/(shell)/missions/detail/page.tsx`**:
   - Enhance `RuntimeQcPanel.tsx` to display `exit_code`, `stderr_preview`, bounded self-repair status (`repair_attempted`, `repair_succeeded`, `initial_verdict`), and the **EDCP Delta Audit Gate** verdict (`delta_audit_gate.audit_result`, `passed`, `pod`, `tolerance_score`, `consumed_at`).
4. **Frontend Unit Tests**:
   - Add/update Vitest unit tests in `apps/mission-control` verifying the upgraded `LogicNodesPage` summary extractor, `RuntimeQcPanel` self-repair/Delta-gate rendering, and `DatabasesPage` diagnostics.

---

## Phase 6: `v1.1.0` Release Alignment, Full Gate Verification & Desktop Rebuild

**Goal:** Align the desktop installer version with `v1.1.0`, sync documentation, pass every lint/test/coverage/doc/audit gate, rebuild and reinstall the Windows desktop application, and push to GitHub.

### Changes
1. **`apps/mission-control/package.json`**:
   - Bump `"version"` from `"0.1.0"` to `"1.1.0"` (and sync `package-lock.json`).
2. **Canonical Documentation Sync**:
   - Update `AGENTS.md`, `README.md`, `docs/CURRENT_TODO.md`, `docs/HANDOFF_CURRENT.md`, and `docs/ELECTRON_INSTALLER.md`.
3. **Full Validation & Desktop Rebuild**:
   - Run `ruff check services shared_runtime tests scripts`, `pytest` with `scripts/check_coverage_thresholds.py` (≥80% global/line, ≥70% branch), `python scripts/validate_documentation.py`, `python scripts/production_review_audit.py`, and `npm --prefix apps/mission-control run test:coverage`.
   - Uninstall the old desktop app, build `theFactory-MissionControl-Setup-1.1.0.exe`, and cleanly install it.
   - Commit and push all updates to `origin/main` and verify all GitHub Actions checks pass.
