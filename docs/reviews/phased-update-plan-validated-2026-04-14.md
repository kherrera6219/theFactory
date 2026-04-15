# theFactory — Validated Phased Update Plan
## Version: Code-Validated
## Date: 2026-04-14
## Based on: HGR_Phased_Update_Plan.docx + codex-baseline-findings-2026-04-14.md
## Reviewer: Claude Code

---

> **This document supersedes the original HGR_Phased_Update_Plan.docx for planning purposes.**
> Every phase below has been validated against actual code state.
> Strikethroughs mark items already complete. Corrections to the original plan are noted inline.

---

## What Changed vs. the Original Plan

| Original Assumption | Code Reality | Impact on Plan |
|---|---|---|
| 4 known production gaps outstanding | DLQ, MCP_API_KEY, AUTH_MODE are **already fixed** | Removed from phased work; only cert path remains |
| Python AST extractor needs to be built | It **already exists and is tested** — 38 test cases in `test_ast_extractor.py` | Phase 5 Wave 1 (Python) is 80% done; just needs wiring |
| Go/Haskell/OCaml are "registry personas" | They have **real pod assignments** in `agent_registry.py:389–418` | Topology section of AGENTS.md needs nuance fix |
| `main.py` is the biggest decomposition target | `storage.py` (1,446 lines, 7 domains) is **larger and riskier** | Phase 6 must start with `storage.py`, not `main.py` |
| UI hardcodes agent states | Production UI is **fully dynamic** — only tests use mock data | Phase 7 UI work is additive (new fields), not corrective |
| No adapter interface exists for lifecycle engines | Confirmed — sequential fallthrough, no ABC/Protocol | Phase 3 still needed as planned |

---

## Pre-Phase: Immediate Fixes (< 1 day, no phase dependency)

These are trivially small and should be done before any phase work begins.

### Fix 1 — `.env.example` cert paths ✅ DONE
**File:** `.env.example:1–5, 32–33`

Added inline comments explaining both contexts at the top of the cert-related URL lines:
Docker containers receive `/run/redis-certs/ca.crt` and `/run/postgres-certs/ca.crt` via
volume mount; local dev outside Docker uses `deploy/.local/...` paths.

### Fix 2 — `layout.tsx` metadata copy ✅ DONE
**File:** `apps/mission-control/app/layout.tsx:22`

Replaced "38-agent multi-language refinery" with
"Multi-agent AI software manufacturing system" — topology-neutral and accurate for all
deployment profiles.

---

## Phase 0: Pre-Validation Setup
**Status: PARTIALLY COMPLETE**
**Remaining work: ~1 day**

| Task | Status | Notes |
|---|---|---|
| Add `AGENTS.md` to repo root | ✅ Done | Expanded with architectural context, topology nuances, lifecycle engine table, extraction engine section, and resolved gaps |
| Create `docs/codex/DEFINITION_OF_DONE.md` | 🔲 Pending | Create from AGENTS.md §6 |
| Create `docs/codex/REVIEW_CHECKLIST.md` | ✅ Fulfilled by this findings doc | Template used successfully |
| Establish `make`/`npm` validation target | 🔲 Pending | Check if `make test` exists at root |
| Establish `codex/` branch convention | ✅ Already used | Branch: `claude/determined-haslett` |

**Exit criteria met?** Partially — AGENTS.md is present, findings doc is produced. Still need `DEFINITION_OF_DONE.md` and a one-command validation target.

---

## Phase 1: Codex Guardrails
**Duration: 1 day | Risk: Low**

**Goal:** Give every future Codex/Claude task a consistent project context and a clear definition of done.

### Tasks

1. **Create `docs/codex/DEFINITION_OF_DONE.md`**
   - Extract the 7 DoD criteria from `AGENTS.md §6` into a standalone checklist
   - Every future task must check this before submitting a PR

2. **Create `docs/codex/REVIEW_CHECKLIST.md`**
   - Distill the review template into a per-PR checklist
   - Include: no test regression, no API contract change without approval, extractor changes need fixture comparison

3. **Add one-command validation target**
   - Check if `Makefile` or `package.json` already has a root-level `test` target
   - If not, add: `make validate` → runs `pytest` (Python services) + `npm test` (MC) + extractor fixture tests
   - Must complete under 5 minutes for CI viability

4. **Update `AGENTS.md §2` topology nuance**
   - Clarify that Go/Haskell/OCaml have real pod assignments (not virtual personas)
   - Clarify that "synthesized heartbeats" applies only to `interface`, `executive`, `support` categories

### Exit Criteria
- `docs/codex/DEFINITION_OF_DONE.md` committed
- `docs/codex/REVIEW_CHECKLIST.md` committed
- One-command validation target exists and runs clean
- `AGENTS.md §2` accurately reflects pod-worker topology

---

## Phase 2: Runtime Truthfulness
**Duration: 3–5 days | Risk: Low**
**Depends on: Phase 1 complete**

**Goal:** Align what operators see with what is actually running. Additive changes only — no behavior changes.

### Tasks

#### 2A — Add `runtime_class` to agent schema
**File:** `services/orchestrator/orchestrator/agent_registry.py`

Add field to every `AgentDefinition` (or equivalent dataclass):
```python
runtime_class: Literal["real_worker", "shared_worker", "synthesized_heartbeat"]
```

- Pod workers (A/B/C/D) → `"shared_worker"` (they share one container per pod)
- PM Agent, CEO/Grand Manager → `"real_worker"` (real processes)
- Interface, Executive, Support → `"synthesized_heartbeat"`

**Why shared_worker not real_worker for pod agents:** Go, Haskell, OCaml etc. run inside a shared pod-worker container, not isolated containers. Only the `full-dedicated-agents` profile gives them isolation.

#### 2B — Expose `runtime_class` in the API
**File:** `services/orchestrator/orchestrator/routes/operations.py`

Add `runtime_class` to the agent record returned by `/internal/operations/agents`.
This is a backward-compatible additive field — no existing consumers break.

#### 2C — Add `topology_mode` to system status
**File:** `services/orchestrator/orchestrator/routes/operations.py`

Add `topology_mode: "condensed" | "dedicated" | "full-dedicated"` derived from:
- Default Docker Compose → `"condensed"`
- `dedicated-agents` profile → `"dedicated"`
- `full-dedicated-agents` profile → `"full-dedicated"`

Derive from an env var `TOPOLOGY_MODE` (default: `"condensed"`).

#### 2D — Mission Control: agent card runtime badge
**File:** `apps/mission-control/app/(shell)/agents/page.tsx`

Add a small badge/chip to each agent card showing `runtime_class`.
Visual distinction: `real_worker` → green, `shared_worker` → blue, `synthesized_heartbeat` → gray/muted.

#### 2E — Mission Control: system status topology indicator
**File:** `apps/mission-control/app/(shell)/` (system status page, TBD location)

Display `topology_mode` alongside service health indicators.

#### 2F — Docs update
Update `docs/ARCHITECTURE.md` and `AGENTS.md §2` to explicitly state:
- Condensed topology is the production default
- Pod workers are shared containers per pod family, not per-language
- Full dedicated topology requires `full-dedicated-agents` compose profile

### What NOT to do in this phase
- Do not convert synthesized agents to real workers
- Do not change heartbeat synthesis logic
- Do not change any API contract (additions only)

### Exit Criteria
- Every agent API record includes `runtime_class`
- `/internal/operations/summary` includes `topology_mode`
- Mission Control agent cards show runtime classification badge
- Docs reflect condensed topology as default

---

## Phase 3: Lifecycle Engine Simplification
**Duration: 5–7 days | Risk: Medium**
**Depends on: Phase 2 complete (event schema must be stable)**

**Goal:** One clean interface for all three lifecycle engines. No behavior change — wrap existing code.

### Tasks

#### 3A — Define `LifecycleEngine` Protocol
**New file:** `services/orchestrator/orchestrator/lifecycle_interface.py`

```python
from typing import Protocol, Callable, Awaitable
from .models import Mission, MissionState

class LifecycleEngine(Protocol):
    async def start_mission(self, mission: Mission, emit: Callable) -> MissionState: ...
    async def advance_phase(self, mission: Mission, emit: Callable) -> MissionState: ...
    async def complete_mission(self, mission: Mission, emit: Callable) -> None: ...
    async def fail_mission(self, mission: Mission, error: str, emit: Callable) -> None: ...
```

#### 3B — Wrap v2 as `MissionFlowV2Engine`
**File:** `services/orchestrator/orchestrator/mission_flow_v2.py`

Add `MissionFlowV2Engine` class that delegates to existing `advance_mission_lifecycle_v2()`.
Existing function stays unchanged — class is a thin wrapper.

#### 3C — Wrap LangGraph as `LangGraphEngine`
**File:** `services/orchestrator/orchestrator/langgraph_lifecycle.py`

Add `LangGraphEngine` class wrapping existing checkpointing logic.
Mark with: `# EXPERIMENTAL — not default. Enabled by LANGGRAPH_ENABLED=true`

#### 3D — Wrap legacy as `LegacyV1Engine`
**File:** `services/orchestrator/orchestrator/runtime.py` (or new `legacy_lifecycle.py`)

Extract legacy v1.1 block into `LegacyV1Engine` class.
Add to class docstring: `# COMPATIBILITY SHIM — not a supported production path. Use MissionFlowV2Engine.`

#### 3E — Factory function
**File:** `services/orchestrator/orchestrator/runtime.py`

```python
def get_lifecycle_engine(settings: Settings) -> LifecycleEngine:
    if settings.mission_flow_v2_enabled:
        return MissionFlowV2Engine()
    if settings.langgraph_enabled:
        return LangGraphEngine()
    return LegacyV1Engine()
```

Replace the inline `if/elif/else` in `advance_mission_lifecycle()` with a call to this factory.

#### 3F — Standardize lifecycle event emission
Verify (with tests) that all three adapter wrappers emit identical event schemas.
Add a shared `assert_lifecycle_event_schema(event)` helper used by all three paths in tests.

### Exit Criteria
- One `LifecycleEngine` Protocol defined
- Three adapter wrappers implemented
- Single factory drives engine selection
- All three adapters covered by tests asserting identical event schema
- Switching engines via config requires zero code changes

---

## Phase 4: Extraction Contract + Fixtures
**Duration: 5–7 days | Risk: Medium**
**Depends on: Phase 1 complete (validation target must exist)**

**Goal:** Define the canonical extractor interface and provenance contract before touching any extractor implementation.

> **Note from validation:** `LanguageExtractor` base class already exists with `.extract() → ExtractionResult`.
> This phase extends the contract with provenance fields, not replaces it.
> The fixture corpus partially exists — `test_language_extractor.py` has inline samples.
> The main work is: add missing provenance fields + externalize fixtures + add golden tests to CI.

### Tasks

#### 4A — Add missing provenance fields to `ExtractedConcept`
**File:** `services/pod-worker/pod_worker/language_extractor.py`

Add to `ExtractedConcept` dataclass:
```python
extraction_method: str = "regex"       # "regex" | "ast" | "tree-sitter"
source_range: tuple[int, int] | None = None  # (start_line, end_line)
```

Update `_detect_concepts()` to populate `extraction_method="regex"` and `source_range`.

#### 4B — Add `extraction_method` to LogicNode payload
**File:** `services/pod-worker/pod_worker/main.py:255–265`

Add `"extraction_method": getattr(concept, "extraction_method", "regex")` to the payload dict.

#### 4C — Externalize fixture corpus
**New directory:** `tests/fixtures/extractors/`

Move inline `PYTHON_SAMPLE`, `JS_SAMPLE`, `RUST_SAMPLE`, etc. from `test_language_extractor.py`
into standalone `.py`/`.js`/`.rs` files in the fixtures directory.

Add expected LogicNode output JSON alongside each source fixture
(e.g. `python_sample_expected.json`).

#### 4D — Golden tests in CI
**File:** `tests/services/test_language_extractor_golden.py` (new)

Add parametrized golden tests: `extractor.extract(fixture_source)` output must match
the expected JSON within a defined tolerance (node count, concept IDs).
These tests fail on regression — they are the gate before any extractor upgrade.

#### 4E — Confirm Python AST extractor provenance parity
Run `extract_python_ast()` on `PYTHON_SAMPLE` and compare to `PythonExtractor().extract()`.
Document the diff: what AST finds that regex misses (and vice versa).
This diff becomes the promotion justification for Phase 5A.

### Exit Criteria
- `ExtractedConcept` has `extraction_method` and `source_range`
- LogicNode payload includes `extraction_method`
- Fixture corpus exists as standalone files for Python, JS, Java at minimum
- Golden tests run as part of CI (`make validate`)
- Python AST vs regex comparison doc committed to `docs/reviews/`

---

## Phase 5: AST Migration — Wave 1
**Duration: 2–3 weeks | Risk: Medium-High**
**Depends on: Phase 4 complete (provenance fields + golden tests must exist)**

**Goal:** Promote Python AST extractor to production. Add JS/TS and Java AST extractors behind feature flags.

> **Note from validation:** Python AST extractor (`ast_extractor.py`) is already built and has 38 tests.
> Wave 1 (Python) is ~80% done. The remaining work is integration, not implementation.

### Wave 1A — Wire Python AST extractor (days 1–3)
**Files:** `services/pod-worker/pod_worker/main.py`, `ast_extractor.py`

1. Add feature flag `PYTHON_AST_EXTRACTOR_ENABLED` (default: `false` for staged rollout)
2. In the extraction path: if flag enabled AND language == "python", call `extract_python_ast()` and map `AstExtractionResult` → `ExtractionResult`
3. Run golden test comparison: AST output vs regex baseline on fixture corpus
4. If node_count(AST) >= node_count(regex) AND all provenance fields populated → promote flag default to `true`
5. Keep regex path accessible behind flag for rollback

**Mapping needed:** `AstFunctionInfo` → `FunctionInfo`, `AstClassInfo` → `ClassInfo`, etc.
These are structurally similar — mapping should be <50 lines.

### Wave 1B — JavaScript/TypeScript AST (days 4–10)
**Approach:** Use `@typescript-eslint/parser` (already available in the MC monorepo's node_modules) or `tree-sitter-javascript`/`tree-sitter-typescript` via Python bindings.

1. Add `js_ast_extractor.py` mirroring the pattern of `ast_extractor.py`
2. Feature flag: `JS_AST_EXTRACTOR_ENABLED`
3. Golden test comparison before promotion

### Wave 1C — Java AST (days 11–21)
**Approach:** `javalang` (pure Python, no JVM required) or `tree-sitter-java`.

1. Add `java_ast_extractor.py`
2. Feature flag: `JAVA_AST_EXTRACTOR_ENABLED`
3. Golden test comparison before promotion

### Promotion criteria (all must pass before defaulting any flag to `true`)

| Criterion | Requirement |
|---|---|
| Node Count | New extractor finds >= old extractor's count on fixture corpus |
| Provenance | All nodes have `confidence`, `extraction_method`, `source_range` populated |
| Audit Pass Rate | Does not regress vs. regex on existing missions |
| Golden Tests | All Phase 4 golden tests pass |

### Exit Criteria
- Python, JS/TS, Java extractors running AST-backed path (flags defaulted to `true`)
- Feature flags available for per-language rollback
- Old regex paths preserved but marked for future removal
- Comparison reports committed to `docs/reviews/`

---

## Phase 6: Orchestrator Slimming
**Duration: 1–2 weeks | Risk: Medium**
**Depends on: Phase 3 complete (lifecycle engine must be behind adapter before splitting)**

**Goal:** Complete the decomposition. No single module mixes more than one domain.

> **Note from validation:** The original plan targets `main.py` first. Code shows `storage.py`
> (1,446 lines, 7+ domains) is the higher-risk target. **Start with `storage.py`.**

### Task Order

#### 6A — Split `storage.py` (highest priority)
**Current:** 1,446 lines handling mission CRUD, events, artifacts, pod assignments, knowledge lake, audit logs, logistics, review approvals.

**Target modules:**
| New Module | Responsibility | Approx Lines |
|---|---|---|
| `mission_store.py` | Mission CRUD, status transitions, queries | ~350 |
| `event_store.py` | Lifecycle event writes and reads | ~150 |
| `artifact_store.py` | Build artifact records, digest tracking | ~200 |
| `audit_store.py` | Audit log entries, compliance records | ~150 |
| `knowledge_store.py` | LogicNode writes, knowledge lake queries | ~200 |
| `logistics_store.py` | Pod assignments, queue depth, routing | ~200 |
| `review_store.py` | Review approvals, gating records | ~150 |

**Approach:** Extract one module at a time. Each extraction gets its own PR and passes the full test suite before the next extraction begins.

#### 6B — Extract heartbeat synthesis from `main.py`
**New file:** `services/orchestrator/orchestrator/heartbeat_service.py`

Move `_build_non_pod_heartbeat_payloads()` (lines 664–730) and `agent_heartbeat_loop()` (lines 733–762) into `HeartbeatService` class.

`main.py` instantiates and starts the service — no logic remains in `main.py` for heartbeats.

#### 6C — Extract review/approval logic from `main.py`
**New file:** `services/orchestrator/orchestrator/review_policy.py`

Move review approval handlers from `main.py` into `ReviewPolicy` class.

#### 6D — Thin `main.py` to composition layer
After 6A–6C, `main.py` should be: FastAPI app init + route registration + service startup. Target: under 500 lines.

#### 6E — Centralize `VALID_TRANSITIONS`
**Current:** Transition rules appear in both `models.py:85–102` and `mission_flow_v2.py`.
**Fix:** Move canonical definition to `models.py`. `mission_flow_v2.py` imports from there.
Add a test that asserts the two sets are identical (until the duplication is removed).

### Exit Criteria
- `storage.py` split into 7 domain modules
- `main.py` under 500 lines
- Heartbeat synthesis in `HeartbeatService`
- `VALID_TRANSITIONS` defined in one place only
- All modules testable without booting the full service

---

## Phase 7: Mission Control UX Accuracy
**Duration: 1–2 weeks | Risk: Low**
**Depends on: Phase 2 complete (backend must expose `runtime_class` and `topology_mode`)**

**Goal:** Operator interface shows what is actually running, not the conceptual architecture model.

### Tasks

#### 7A — Active Runtime vs. Conceptual Architecture views
Add a toggle on the Agents page: "Active Runtime" vs. "Architecture Diagram".
- Active Runtime: live API data, `runtime_class` badges, real heartbeat timestamps
- Architecture Diagram: the 38-agent canonical model (clearly labeled "Full Dedicated Topology")

#### 7B — Mission Detail: lifecycle engine indicator
**File:** `apps/mission-control/app/(shell)/missions/[id]/page.tsx`

Add a badge showing the active lifecycle engine: `Mission Flow v2` | `LangGraph (experimental)` | `Legacy v1.1 (compatibility)`.
Backend: add `lifecycle_engine: str` to the mission record API response.

#### 7C — Mission completion: audit evidence panel
**File:** `missions/[id]/page.tsx`

Add "Audit Evidence" section on completion:
- Audit report ID
- Artifact hashes (`digest_sha256` — already in `MissionBuildArtifactRecord`)
- Approval chain (who approved, at what phase, at what timestamp)
- Link to full audit log

#### 7D — System status: topology mode indicator
Add `topology_mode` (from Phase 2C) to the system status view.

#### 7E — Feature flag warnings
When a mission action requires an optional profile (e.g. dedicated agents) or a disabled feature flag, show an inline warning in the UI rather than silently failing.

### Exit Criteria
- Operator can determine what is actually live without reading source code
- No UI screen implies a full dedicated 38-agent topology unless that profile is active
- Mission completion shows verifiable evidence (audit report ID, artifact hash, approval chain)
- Active lifecycle engine is visible on Mission Detail

---

## Execution Order Summary

| Step | Action | Duration | Risk |
|---|---|---|---|
| ~~Now~~ ✅ | Fix `.env.example` cert paths | Done | None |
| ~~Now~~ ✅ | Fix `layout.tsx` "38-agent" copy | Done | None |
| Week 1 | Phase 1 — Codex Guardrails | 1 day | Low |
| Week 1–2 | Phase 2 — Runtime Truthfulness | 3–5 days | Low |
| Week 2–3 | Phase 3 — Lifecycle Simplification | 5–7 days | Medium |
| Week 3–4 | Phase 4 — Extraction Contract + Fixtures | 5–7 days | Medium |
| Week 4–7 | Phase 5 — AST Migration Wave 1 | 2–3 weeks | Med-High |
| Week 5–7 (parallel) | Phase 6 — Orchestrator Slimming | 1–2 weeks | Medium |
| Week 7–9 (parallel) | Phase 7 — Mission Control UX | 1–2 weeks | Low |
| Ongoing | AST Waves 2–5 (JS/TS in Wave 1; Java, Rust, Go, others follow) | Background | Med-High |

---

## Appendix: Items Removed from the Original Plan (Already Done)

These items were listed as "Known Open Gaps" in `HGR_Phased_Update_Plan.docx` and `AGENTS.md §4`
but are already resolved in the current codebase:

| Gap | Resolution | Evidence |
|---|---|---|
| DLQ on intake stream | `_write_intake_dlq()` using `redis.xadd()` with `xack` confirmation | `orchestrator/runtime.py:394–506` |
| MCP_API_KEY instability | Production raises `RuntimeError` if key not set; dev auto-gen logs loud warning | `semantic-bus-mcp/mcp_server.py:32–47` |
| Silent AUTH_MODE fallback | Production raises `RuntimeError` on invalid value; dev falls back with `LOGGER.error()` | `api-gateway/main.py:152–167` |

**These should be removed from `AGENTS.md §4`** to avoid Codex agents spending cycles re-investigating resolved issues.
