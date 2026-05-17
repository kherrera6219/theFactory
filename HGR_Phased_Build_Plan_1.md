# theFactory / Holy Grail Refinery
## Phased Build Plan — Current State to Full Operation
**Date:** May 2026 | **Basis:** Live code review + full spec review + gap analysis

---

## Superseded Validation Note - May 17, 2026

This document is retained as a historical alternate plan. Do not use it as the
current source of truth for phase status or model selections. The active plan is
`HGR_Phased_Build_Plan.md`, with the detailed per-phase files carrying current
validation notes.

Key drift in this file:

- Phase 1 model recommendations are stale. Current project defaults are
  `gpt-5.5`, `gpt-5.3-codex`, `claude-opus-4-7`, `claude-sonnet-4-6`,
  `gemini-3.1-pro-preview`, and `gemini-3.1-flash-lite`.
- Phases 1-5 have already shipped material implementation work, including PM
  feature contracts, mission charters, CEO mission contracts, generated output
  artifact support, and logic cluster decomposition.
- The next active implementation target is Phase 6 pod group standards, followed
  by Phase 7 Java/JS AST activation and Phases 8-11 Smelt-Cycle completion.

---

## How to Read This Plan

Each phase has a clear **entry state** (what the system can do before you start),
**exit state** (what it can do when you finish), **exact files to change**, and
**validation criteria** that prove the phase is done before moving to the next one.

Phases are sequenced so that each one produces a visible, testable result.
No phase exists purely to enable a future phase — every phase ships something
a user or developer can demonstrate.

The plan is divided into five tiers:

- **Tier 1 — First Working Loop** (Phases 1–3): System produces actual output for the first time
- **Tier 2 — Intelligence Layer** (Phases 4–7): Agents think, not just route
- **Tier 3 — Full Smelt-Cycle** (Phases 8–11): Complete 7-phase pipeline end-to-end
- **Tier 4 — Quality and Trust** (Phases 12–15): Verification, compliance, cost tracking
- **Tier 5 — Production Operations** (Phases 16–18): Self-sustaining, enterprise-ready

---

# TIER 1 — FIRST WORKING LOOP
## Goal: The system produces actual software output for the first time

---

## Phase 1 — Fix the Model Layer
**Duration:** 1–2 days
**Entry state:** LLM delegation calls always fall back deterministically because model strings are invalid
**Exit state:** Real LLM calls succeed for CEO, pod-manager, and specialist routing steps

### What to do

**1. Update model strings in `services/orchestrator/orchestrator/agent_integrations.py`**

Replace the `_LLM_PROFILES` dict with valid current model names:

```python
# Executive and orchestration — deep reasoning
"openai_exec": {
    "provider": "openai",
    "model": "gpt-5.5",
    "fallback_provider": "anthropic",
    "fallback_model": "claude-opus-4-7",
}

# Code generation specialists
"openai_codegen": {
    "provider": "openai",
    "model": "gpt-5.3-codex",
    "fallback_provider": "anthropic",
    "fallback_model": "claude-sonnet-4-6",
}

# Audit and review
"anthropic_general_audit": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
}
"anthropic_deep_audit": {
    "provider": "anthropic",
    "model": "claude-opus-4-7",
}

# STEM / math / knowledge
"gemini_stem": {
    "provider": "gemini",
    "model": "gemini-3.1-pro-preview",
    "fallback_provider": "openai",
    "fallback_model": "gpt-5.5",
}
"gemini_ops_fast": {
    "provider": "gemini",
    "model": "gemini-3.1-flash-lite",
    "fallback_provider": "openai",
    "fallback_model": "gpt-5.5",
}
```

**2. Update `apps/mission-control/app/(shell)/settings/page.tsx`**

Update `STATIC_AGENT_SLOTS` to reflect the new model names for the vault UI display.

**3. Update `deploy/promotion-policy.json`**

Confirm `blocked_lifecycle_stages` list does not accidentally block the new models.
Run `python scripts/export_agent_model_inventory.py` and verify all agents
show `"lifecycle": "stable"` and `"production_approved": true`.

### Files changed
- `services/orchestrator/orchestrator/agent_integrations.py`
- `apps/mission-control/app/(shell)/settings/page.tsx`
- `deploy/promotion-policy.json`

### Validation
```bash
python scripts/export_agent_model_inventory.py --output-file /tmp/model-check.json
# All agents must show production_approved: true

make test
# All tests pass — no regressions from model string changes
```

---

## Phase 2 — CEO Generative Prompt (Refined-IR Contract Production)
**Duration:** 3–5 days
**Entry state:** CEO LLM call returns routing only (pod_manager_agent_id, specialist_agent_id, rationale)
**Exit state:** CEO produces a structured Refined-IR Contract that specifies what LogicNodes the mission requires

### What to do

**1. Replace the CEO prompt in `services/orchestrator/orchestrator/llm_delegation.py`**

The `_build_prompt()` function currently asks for routing only. Replace it with a
two-stage call:

*Stage 1 (routing — keep existing):* Returns `pod_manager_agent_id`, `specialist_agent_id`.
*Stage 2 (new — contract generation):* Returns structured mission contract.

Add a new function `generate_refined_ir_contract()`:

```python
async def generate_refined_ir_contract(
    *,
    mission_context: dict[str, Any],
    ceo_delegation: dict[str, Any],
) -> dict[str, Any]:
    """CEO produces the Refined-IR Contract — what LogicNodes are required."""
    recommendation = _ceo_recommendation()
    prompt = _build_contract_prompt(
        mission_context=mission_context,
        ceo_delegation=ceo_delegation,
        recommended_provider=recommendation["provider"],
        recommended_model=recommendation["model"],
    )
    parsed, provider, model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context="ceo refined-ir contract",
    )
    if not isinstance(parsed, dict):
        return _fallback_refined_ir_contract(mission_context, ceo_delegation)
    return _normalize_refined_ir_contract(parsed, provider, model, route)
```

The new prompt instructs the CEO to produce:
```json
{
  "contract_summary": "One sentence describing what will be built",
  "target_language": "python",
  "mission_type": "BUILD_NEW",
  "required_domains": ["list_operations", "http_client", "data_persistence"],
  "logicnode_requirements": [
    {
      "domain": "http_client",
      "concept": "get_request",
      "intent": "Send HTTP GET and return parsed JSON response",
      "priority": "HIGH"
    }
  ],
  "acceptance_criteria": ["string array of testable criteria"],
  "output_format": "standalone_script | library | service | binary"
}
```

**2. Store contract in mission metadata**

In `mission_flow_v2.py`, after CEO delegation succeeds, call
`generate_refined_ir_contract()` and store the result in
`metadata["refined_ir_contract"]`.

**3. Expose contract in mission chain trace**

In `services/orchestrator/orchestrator/routes/internal.py`,
include `refined_ir_contract` in `_build_mission_chain_trace()` output.

**4. Display on Mission Detail page**

In `apps/mission-control/app/(shell)/missions/[id]/page.tsx`,
render the contract summary and logicnode requirements in the
Mission Signals panel alongside the existing chain trace.

### Files changed
- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/orchestrator/orchestrator/routes/internal.py`
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`

### Validation
Submit a test mission with `ANALYZE_ONLY` type and a clear Python prompt.
Inspect the chain trace — `metadata.refined_ir_contract` must be present
with at least one `logicnode_requirements` entry.

```bash
# Live stack validation
LIVE_STACK_ENABLED=1 pytest tests/services/test_live_mission_flow_integration.py -v
# Inspect chain trace response for refined_ir_contract field
```

---

## Phase 3 — Specialist Code Generation (SQUEEZE Activation)
**Duration:** 5–7 days
**Entry state:** Specialist `execute()` validates logicnode structure only; no code is produced
**Exit state:** Specialist agents generate target-language code from LogicNodes; mission output artifact contains generated code

### What to do

This is the most important phase in the entire plan. It is what makes theFactory
produce software for the first time.

**1. Add `generate_code_from_logicnodes()` to `llm_delegation.py`**

```python
async def generate_code_from_logicnodes(
    *,
    mission_context: dict[str, Any],
    specialist_agent_id: str,
    logicnodes: list[dict[str, Any]],
    refined_ir_contract: dict[str, Any],
    target_language: str,
) -> dict[str, Any]:
    """Specialist generates code from extracted LogicNodes and contract."""
    agent = _resolve_agent(specialist_agent_id)
    recommendation = _agent_recommendation(specialist_agent_id)
    prompt = _build_codegen_prompt(
        mission_context=mission_context,
        agent=agent,
        logicnodes=logicnodes,
        contract=refined_ir_contract,
        target_language=target_language,
        recommended_provider=recommendation["provider"],
        recommended_model=recommendation["model"],
    )
    parsed, provider, model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"specialist codegen {specialist_agent_id}",
    )
    if not isinstance(parsed, dict):
        return _fallback_codegen(specialist_agent_id, logicnodes, target_language)
    return _normalize_codegen_result(parsed, provider, model, route)
```

The specialist prompt provides:
- The Refined-IR Contract (what to build)
- All extracted LogicNodes (the semantic patterns found in source)
- Target language
- Specialist persona and extraction guidance

It requests back:
```json
{
  "generated_code": "complete source code string",
  "language": "python",
  "filename": "solution.py",
  "description": "What was generated",
  "test_cases": ["list of test case descriptions"],
  "dependencies": ["any required imports or packages"]
}
```

**2. Wire codegen into `mission_flow_v2.py` at the RUNNING → GATING transition**

After logicnodes are persisted, call `generate_code_from_logicnodes()` if:
- `refined_ir_contract` is present in metadata
- `logicnodes` count > 0
- `output_mode` is not `ANALYZE_ONLY`

Store result in `metadata["generated_output"]`.

**3. Update `build_artifacts.py` to package generated code**

When `metadata["generated_output"]` is present, use it as the artifact content
instead of the input `source_code`. The existing SHA-256 digest, manifest,
and chain-of-custody machinery already handles packaging — just point it
at the generated content.

**4. Display generated output on Mission Detail page**

Add a "Generated Output" panel to the mission detail view that renders:
- The generated code in a syntax-highlighted code block
- Filename and language
- Description
- Dependencies
- Download button

### Files changed
- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/orchestrator/orchestrator/build_artifacts.py`
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
- `apps/mission-control/app/lib/types.ts` (add generated output types)

### Validation
This phase is validated by a working demo mission:

```bash
# Submit this via the Chat page or API:
POST /v1/missions
{
  "prompt": "Write a Python function that reads a CSV file and returns a list of dicts",
  "requested_target_language": "python",
  "mission_type": "BUILD_NEW",
  "output_mode": "FULL_BUILD"
}

# Expected: Mission reaches COMPLETE with metadata.generated_output containing
# valid Python code that implements the requested function.
```

**Tier 1 is complete when this demo works end-to-end.**

---

# TIER 2 — INTELLIGENCE LAYER
## Goal: Every agent in the pipeline thinks and produces real work

---

## Phase 4 — PM Agent Cognition (Feature Contract + Mission Charter)
**Duration:** 3–5 days
**Entry state:** PM intake stores user prompt as plain text; feature contract is a local UI preview only
**Exit state:** PM Agent makes a real LLM call, produces a structured Feature Contract and Mission Charter, stores both in mission metadata

### What to do

**1. Activate PM LLM call in `mission_flow_v2.py` at the PM_INTAKE phase**

Add `generate_pm_feature_contract()` to `llm_delegation.py`:

```python
async def generate_pm_feature_contract(
    *,
    mission_context: dict[str, Any],
    prompt: str,
    mission_type: str,
    depth_mode: str,
) -> dict[str, Any]:
    """PM Agent translates user vibe into structured Feature Contract."""
```

The PM prompt instructs the PM agent to produce:
```json
{
  "title": "Short mission title",
  "summary": "One-paragraph description of what will be built",
  "functional_requirements": ["list of what the system must do"],
  "non_functional_requirements": ["performance, security, reliability needs"],
  "acceptance_criteria": ["testable pass/fail criteria"],
  "target_languages": ["primary", "secondary"],
  "complexity": "low | medium | high | very_high",
  "estimated_logicnode_count": 15,
  "risk_notes": ["potential challenges"]
}
```

**2. Generate Mission Charter from Feature Contract**

Use `schemas/mission_charter.v1.json` as the output schema.
After PM produces the Feature Contract, generate and validate a
Mission Charter conforming to the existing schema. Store in
`metadata["mission_charter"]`.

**3. Update Chat page to reflect real PM cognition**

The Chat page currently generates a preview with hardcoded templates.
Replace the `createBuilderPreview()` call with a call that reaches the
new PM intake endpoint. Display the structured Feature Contract in the
chat UI before mission launch.

**4. Display Mission Charter on Mission Detail page**

Add a "Mission Charter" collapsible panel showing the formal charter.

### Files changed
- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `apps/mission-control/app/(shell)/chat/page.tsx`
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
- `apps/mission-control/app/api/builder/review/route.ts` (update to use real PM call)

### Validation
Submit a vague prompt like "build me a crypto price tracker."
Mission Charter in the chain trace must contain structured functional requirements,
not just the raw prompt string.

---

## Phase 5 — CEO Logic Cluster Decomposition
**Duration:** 3–4 days
**Entry state:** CEO routing now creates a `mission_contract` and `logic_clusters`; pod workers do not yet consume those clusters for focused extraction.
**Exit state:** CEO produces Logic Clusters — explicit pod assignments with domain scope per cluster — which drive what each pod actually works on

### What to do

**1. Extend `generate_ceo_delegation()` to produce Logic Clusters**

After routing decision, CEO makes a second call:

```python
async def generate_logic_clusters(
    *,
    feature_contract: dict[str, Any],
    mission_context: dict[str, Any],
) -> list[dict[str, Any]]:
    """CEO decomposes mission into Logic Clusters assigned to pods."""
```

Returns:
```json
[
  {
    "cluster_id": "cluster-ui",
    "cluster_name": "UI and Rendering",
    "assigned_pod": "podA",
    "domains": ["dom_events", "string_manipulation", "list_operations"],
    "description": "Handle all user interface rendering and event logic",
    "priority": "HIGH"
  },
  {
    "cluster_id": "cluster-data",
    "assigned_pod": "podC",
    "domains": ["data_persistence", "query_operations"],
    "description": "Database access and data model",
    "priority": "HIGH"
  }
]
```

**2. Wire Logic Clusters into pod-worker routing**

Store Logic Clusters in `metadata["logic_clusters"]`.
Pod workers filter their language extraction to the domains in their
assigned cluster rather than extracting everything.

**3. Display Logic Clusters in Mission Detail**

Add a "Logic Clusters" panel showing which pods are assigned which
work domains.

### Files changed
- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/pod-worker/pod_worker/main.py`
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`

---

## Phase 6 — Sub-Manager Consolidation (Pod Group Standards)
**Duration:** 4–5 days
**Entry state:** Pod managers produce a routing stub; no cross-language LogicNode deduplication
**Exit state:** Pod Sub-Managers consolidate 4 specialists' LogicNodes into Pod Group Standards, eliminating cross-language duplicates

### What to do

**1. Add `generate_pod_group_standard()` to `llm_delegation.py`**

After all specialists in a pod have written their logicnodes, the Sub-Manager
makes an LLM call that:
- Receives all logicnodes from the 4 pod specialists
- Identifies semantic equivalents across languages (Python filter ≈ JS .filter() ≈ Ruby select)
- Produces a deduplicated Pod Group Standard

```python
async def generate_pod_group_standard(
    *,
    pod_name: str,
    pod_manager_agent_id: str,
    logicnodes_by_language: dict[str, list[dict]],
    mission_context: dict[str, Any],
) -> dict[str, Any]:
    """Sub-Manager consolidates specialist outputs into Pod Group Standard."""
```

Returns:
```json
{
  "pod": "podA",
  "canonical_logicnodes": [...],
  "eliminated_duplicates": 12,
  "cross_language_coverage": {
    "all_four": 8,
    "three": 4,
    "two": 6
  }
}
```

**2. Trigger consolidation at the right lifecycle point**

In `mission_flow_v2.py`, after all specialists in a pod have written
their logicnodes (detectable via logicnode counts per language), trigger
the Sub-Manager consolidation call. Store result in
`metadata["pod_group_standards"][pod_name]`.

**3. Add pod standard data to operations API**

Expose `pod_group_standards` in the chain trace so Mission Detail can
display what each pod's consolidated output looked like.

---

## Phase 7 — Java and JS/TS AST Extractors (Real Wave 1 Completion)
**Duration:** 2–3 days
**Entry state:** Java and JS/TS AST extractors are stubs returning `success=False`
**Exit state:** Java and JS/TS extraction uses real AST parsing with same quality as Python

### What to do

**1. Java — activate `javalang`**

In `services/pod-worker/requirements.txt`, add `javalang==0.13.*`.

In `java_ast_extractor.py`, implement `extract_java_ast()` using `javalang`:
- Parse the source with `javalang.parse.parse()`
- Walk the AST for `MethodDeclaration`, `ClassDeclaration`, `InterfaceDeclaration`
- Extract modifiers, annotations, return types, parameter types
- Mirror the `AstExtractionResult` pattern from `ast_extractor.py`

Add `JAVA_AST_EXTRACTOR_ENABLED` env var wired in `pod_worker/main.py`.

**2. JavaScript/TypeScript — activate `esprima`**

In `services/pod-worker/requirements.txt`, add `esprima==4.*`.

In `js_ast_extractor.py`, implement `extract_js_ast()` using `esprima`:
- Parse with `esprima.parseScript()` / `esprima.parseModule()`
- Walk for `FunctionDeclaration`, `ClassDeclaration`, `ArrowFunctionExpression`,
  `ImportDeclaration`, `ExportNamedDeclaration`
- Handle TypeScript by stripping type annotations before parsing
  (or add `@typescript-eslint/parser` via subprocess call)

Add `JS_AST_EXTRACTOR_ENABLED` env var wired in `pod_worker/main.py`.

**3. Add fixture tests**

Add fixture files to `tests/fixtures/extractors/`:
- `java_complex_sample.java` with inner classes, generics, annotations
- `typescript_sample.ts` with interfaces, generics, async functions

Add golden tests to `test_language_extractor_golden.py` locking the output.

### Files changed
- `services/pod-worker/requirements.txt`
- `services/pod-worker/pod_worker/java_ast_extractor.py`
- `services/pod-worker/pod_worker/js_ast_extractor.py`
- `services/pod-worker/pod_worker/main.py`
- `tests/fixtures/extractors/java_complex_sample.java`
- `tests/fixtures/extractors/typescript_sample.ts`
- `tests/services/test_language_extractor_golden.py`

---

# TIER 3 — FULL SMELT-CYCLE
## Goal: The complete 7-phase pipeline runs end-to-end as designed

---

## Phase 8 — FETCH Phase — IS Agent and Knowledge Lake
**Duration:** 7–10 days
**Entry state:** Specialists extract with no documentation context; extraction is structural only
**Exit state:** IS Agent indexes required documentation before extraction begins; specialists receive relevant context

### What to do

**1. Create `services/orchestrator/orchestrator/knowledge_lake.py`**

Implement the Knowledge Lake as a Qdrant-backed service (Qdrant is already running):
- `index_documentation(language, library, content)` — chunk, embed, upsert to Qdrant
- `query_documentation(language, concept, top_k)` — semantic search
- `is_stocked(language, library)` — check if docs exist
- `broadcast_knowledge_ready(languages)` — publish Protocol Sigma event

Use a lightweight embedding approach initially — hash-based deterministic vectors
(already in `qdrant_store.py`) are fine for structure; upgrade to real embeddings
in Tier 4.

**2. Create `services/orchestrator/orchestrator/is_agent.py`**

Implement the IS Agent execution loop:
```python
async def run_fetch_phase(
    *,
    app: Any,
    mission_id: str,
    required_languages: list[str],
    required_libraries: list[str],
) -> dict[str, Any]:
    """Fetch phase: index required documentation and broadcast knowledge_ready."""
```

For each required language:
- Check Knowledge Lake — already stocked?
- If not: fetch documentation from a curated static source set first
  (Python stdlib docs, MDN for JS, etc.) then expand to live crawling
- Index into Qdrant
- Publish `knowledge_ready` event via Protocol Sigma

**3. Wire FETCH phase into mission_flow_v2.py**

Add a `FETCH` state between `PM_INTAKE` and `CEO_DELEGATED` (or run concurrently).
The IS Agent activates when the mission scope is known (after PM_INTAKE).
CEO delegation waits for `knowledge_ready` events before proceeding.

**4. Inject documentation context into specialist extraction**

In `pod_worker/main.py`, before running `extractor.extract()`, query the
Knowledge Lake for relevant docs for the target language and attach
as context to the extraction. Initially this supplements the regex/AST
extraction rather than replacing it.

**5. Add Protocol Sigma publisher in semantic-bus-mcp**

Ensure Protocol Sigma `knowledge_type: "documentation"` events flow through
the semantic bus from IS Agent to subscribers.

### Files changed
- `services/orchestrator/orchestrator/knowledge_lake.py` (new)
- `services/orchestrator/orchestrator/is_agent.py` (new)
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/pod-worker/pod_worker/main.py`
- `services/orchestrator/orchestrator/models.py` (add FETCH state)
- `apps/mission-control/app/lib/smelt-cycle.ts` (add FETCH to phase map)

---

## Phase 9 — FUSION Phase — CEO Logic Folding (Master Logic Stream)
**Duration:** 5–7 days
**Entry state:** FUSION checkpoint fires but nothing executes; LogicNodes from different pods are unrelated
**Exit state:** CEO performs real cross-pod LogicNode fusion, producing a unified Master Logic Stream

### What to do

**1. Add `generate_master_logic_stream()` to `llm_delegation.py`**

After all pod group standards are produced, CEO performs Logic Folding:

```python
async def generate_master_logic_stream(
    *,
    pod_group_standards: dict[str, dict],
    refined_ir_contract: dict[str, Any],
    mission_context: dict[str, Any],
) -> dict[str, Any]:
    """CEO fuses 4 Pod Group Standards into unified Master Logic Stream."""
```

CEO prompt receives:
- All 4 Pod Group Standards (deduplicated logicnodes per pod)
- The Refined-IR Contract (what was requested)
- Instruction to: deduplicate across pods, resolve conflicts,
  order by dependency, produce a single ordered sequence

Returns:
```json
{
  "master_logic_stream": [
    {
      "node_id": "unified-001",
      "domain": "http_client",
      "concept": "get_request",
      "canonical_intent": "Send HTTP GET and return parsed JSON",
      "source_pods": ["podA", "podC"],
      "confidence": 0.94,
      "dependency_order": 1
    }
  ],
  "total_unified_nodes": 18,
  "eliminated_across_pods": 7,
  "ready_for_codegen": true
}
```

**2. Store Master Logic Stream in mission metadata**

Store in `metadata["master_logic_stream"]`. Update `generate_code_from_logicnodes()`
(Phase 3) to use the Master Logic Stream as input when available, falling back
to raw logicnodes.

**3. Display Master Logic Stream on Mission Detail page**

Add a "Master Logic Stream" panel that shows the unified node list with
source pod attribution and dependency ordering.

---

## Phase 10 — DELIVERY Phase — PM Visual Verification and Output Presentation
**Duration:** 4–5 days
**Entry state:** Mission completes with no delivery action; user sees audit trace but no clear deliverable
**Exit state:** PM Agent presents the generated output to the user with a clear delivery summary; Delivery panel prominently displays the artifact

### What to do

**1. Add `generate_pm_delivery_summary()` to `llm_delegation.py`**

At mission COMPLETE, PM Agent makes a final LLM call:
```python
async def generate_pm_delivery_summary(
    *,
    mission_context: dict[str, Any],
    generated_output: dict[str, Any],
    feature_contract: dict[str, Any],
) -> dict[str, Any]:
    """PM Agent produces delivery summary and validates output against intent."""
```

Returns:
```json
{
  "delivery_title": "Python CSV Reader Function",
  "delivery_summary": "Delivered a Python function that reads CSV files and returns list of dicts. All acceptance criteria met.",
  "criteria_met": ["criterion 1", "criterion 2"],
  "criteria_unmet": [],
  "recommendations": ["Consider adding error handling for malformed CSV"],
  "next_steps": ["Test with your actual CSV files", "Add type hints for stricter validation"]
}
```

Store in `metadata["delivery_summary"]`.

**2. Add prominent DELIVERY panel to Mission Detail page**

When `state === "COMPLETE"` and `delivery_summary` exists:
- Show a full-width "Mission Delivered" banner
- Display the delivery summary prominently
- Show the generated code with syntax highlighting and a copy/download button
- List criteria met/unmet
- Show next steps

**3. Add a download endpoint to the API Gateway**

```
GET /v1/missions/{id}/artifact
```

Returns the generated code as a downloadable file with correct MIME type
and filename from the generated output metadata.

### Files changed
- `services/orchestrator/orchestrator/llm_delegation.py`
- `services/orchestrator/orchestrator/mission_flow_v2.py`
- `services/api-gateway/api_gateway/main.py` (add /artifact endpoint)
- `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
- `apps/mission-control/app/lib/api-client.ts`

---

## Phase 11 — Application Intelligence Map (AIM) Generation
**Duration:** 5–7 days
**Entry state:** IMPORT_MODERNIZE/PORT/DEBUG_REPAIR missions run standard extraction with no pre-analysis
**Exit state:** Analysis missions produce a formal AIM artifact before any work begins; operator reviews and approves before proceeding

### What to do

**1. Create `services/orchestrator/orchestrator/aim_generator.py`**

```python
async def generate_application_intelligence_map(
    *,
    mission_id: str,
    source_code: str,
    mission_type: str,
    mission_context: dict[str, Any],
) -> dict[str, Any]:
    """Generate a comprehensive read-only analysis of the target application."""
```

The AIM generator:
- Runs all language extractors against the source bundle
- Groups findings by: language mix, function count, class count, import graph,
  concept distribution by domain
- Makes a CEO LLM call to synthesize findings into structured analysis
- Produces the AIM conforming to `APPLICATION_INTELLIGENCE_MAP.md` spec

Stores result in `metadata["application_intelligence_map"]`.

**2. Gate analysis-type missions behind AIM approval**

For `IMPORT_MODERNIZE`, `PORT`, `DEBUG_REPAIR`, `SECURITY_HARDEN`,
`REDUCE_DEPENDENCIES`, `ANALYZE_ONLY` missions in PRODUCTION/REGULATED depth:
- Produce AIM after PM_INTAKE
- Set `human_approval_required: true` in mission charter
- Block CEO delegation until operator reviews and approves the AIM

**3. Add AIM viewer to Mission Detail page**

Show: language distribution chart, top domains detected, dependency graph summary,
recommended mission approach, risk assessment.

---

# TIER 4 — QUALITY AND TRUST
## Goal: The verification, compliance, and cost guarantees from the spec are real

---

## Phase 12 — Equivalence Verification Harness
**Duration:** 7–10 days
**Entry state:** Audit gate checks node_id and concept field presence only
**Exit state:** Audit agents run real equivalence tests comparing original code behavior against LogicNode specification

### What to do

**1. Create `services/orchestrator/orchestrator/equivalence_tester.py`**

```python
async def run_equivalence_tests(
    *,
    logicnode: dict[str, Any],
    source_code: str,
    language: str,
    test_count: int = 100,  # Start at 100, scale to 1000 in production
) -> dict[str, Any]:
    """Run equivalence tests between LogicNode and original source behavior."""
```

Approach:
- Use the LLM to generate `test_count` test inputs appropriate for the LogicNode's
  domain and concept
- Use the LLM to predict expected outputs based on the LogicNode specification
- Compare structural consistency (not execution — execution requires sandboxing)
- Produce a confidence score and pass/fail verdict
- Flag logicnodes below the configured tolerance threshold

**2. Add sandbox execution path (optional, gated by flag)**

For Python logicnodes: use `multiprocessing` with timeout and memory limit
to actually execute both the original code and a LogicNode-derived stub.
Gate behind `EQUIVALENCE_SANDBOX_ENABLED` flag. Start off.

**3. Wire into `PodAuditAgent.execute()` in `agent_base.py`**

Replace the current stub validation with:
```python
def execute(self, mission_id: str, payload: dict[str, Any]) -> AgentResult:
    logicnodes = payload.get("logicnodes", [])
    source_code = payload.get("source_payload", "")
    language = payload.get("requested_target_language", "python")
    
    # Run equivalence tests for each logicnode
    for node in logicnodes:
        result = await run_equivalence_tests(
            logicnode=node,
            source_code=source_code,
            language=language,
        )
        if result["passed"] is False:
            # Route rejection back through Protocol Delta
```

---

## Phase 13 — Compliance and Security Agent Activation
**Duration:** 5–7 days
**Entry state:** Compliance and Security agents are synthesized heartbeats only
**Exit state:** Real compliance and security checks run on every LogicNode

### What to do

**1. Activate Compliance Agent (AGENT-08)**

Create `services/orchestrator/orchestrator/compliance_agent.py`:

```python
async def check_logicnode_compliance(
    *,
    logicnode: dict[str, Any],
    source_reference: str,
    source_language: str,
) -> dict[str, Any]:
    """Check LogicNode for license compatibility and IP provenance."""
```

- Detect source library from `source_reference` field
- Look up known license for detected library
- Flag GPL/AGPL/LGPL contamination
- Produce compliance verdict: `CLEAR | FLAGGED | BLOCKED`

Wire into `mission_flow_v2.py` as a parallel check during RUNNING phase.

**2. Activate Security Agent (AGENT-05)**

Create `services/orchestrator/orchestrator/security_agent.py`:

```python
async def scan_logicnode_security(
    *,
    logicnode: dict[str, Any],
    generated_code: str | None = None,
) -> dict[str, Any]:
    """Scan LogicNode and generated code for security issues."""
```

- Check concept domain for known dangerous patterns
  (e.g., `system_calls` → check for injection risk, `crypto` → check for weak algorithms)
- If `generated_code` is present, scan for OWASP Top 10 patterns
- Produce security verdict: `PASS | WARNING | BLOCK`

**3. Add security/compliance reports to Mission Detail**

Display compliance and security scan results in the audit panel.

---

## Phase 14 — Dependency Absorption Engine (DEPABS)
**Duration:** 10–14 days
**Entry state:** REDUCE_DEPENDENCIES missions run standard extraction; no absorption logic
**Exit state:** DEPABS agent scans dependencies, classifies them, generates first-party replacement code, and eliminates absorbable dependencies from output

### What to do

**1. Create `services/orchestrator/orchestrator/depabs_agent.py`**

```python
async def analyze_dependencies(
    *,
    source_code: str,
    language: str,
    imports: list[str],
) -> dict[str, Any]:
    """Classify all detected dependencies by absorbability."""
```

For each detected import:
- Classify: Absorb / Replace / Wrap / Pin / Keep / Block
- For "Absorb" classification: identify which symbols are actually used
- Document justification for each decision

```python
async def absorb_dependency(
    *,
    library_name: str,
    used_symbols: list[str],
    source_language: str,
    target_language: str,
    logicnodes: list[dict],
) -> dict[str, Any]:
    """Generate first-party replacement for an absorbable dependency."""
```

Uses the specialist LLM to generate the replacement code for just the
used symbols, not the entire library.

**2. Wire into REDUCE_DEPENDENCIES mission type**

In `mission_flow_v2.py`, missions with `mission_type == "REDUCE_DEPENDENCIES"`
trigger the DEPABS pipeline:
1. Analyze all dependencies
2. For each "Absorb" decision: generate replacement
3. Produce a dependency report and modified source
4. Package modified source as the output artifact

**3. Display absorption report in Mission Detail**

Show: original dependency list, classification per library, generated replacements,
dependency count before/after, estimated size reduction.

---

## Phase 15 — Accountant Agent — Token Cost Ledger
**Duration:** 2–3 days
**Entry state:** No token tracking; API cost per mission is unknown
**Exit state:** Every LLM call is tracked; per-mission cost is recorded and visible in Mission Control

### What to do

**1. Add cost tracking wrapper to all LLM calls in `llm_delegation.py`**

```python
async def _tracked_call(*args, call_context: str, mission_id: str, **kwargs):
    """Wrap any LLM call with token cost tracking."""
    result = await _call_with_recommendation(*args, **kwargs)
    # Extract token counts from response headers/body
    # POST to /internal/missions/{id}/token-usage
    return result
```

**2. Add token-usage table to PostgreSQL (V006 migration)**

```sql
CREATE TABLE IF NOT EXISTS mission_token_usage (
    id BIGSERIAL PRIMARY KEY,
    mission_id TEXT NOT NULL REFERENCES missions(mission_id) ON DELETE CASCADE,
    agent_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    call_context TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd DECIMAL(10, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

**3. Add cost summary to Mission Detail page**

Show: total cost, cost per agent, cost per phase, running total vs budget.

**4. Add cost alert**

If mission cost exceeds `$5.00` threshold, emit a Protocol Rho alert and
display a warning in Mission Control.

---

# TIER 5 — PRODUCTION OPERATIONS
## Goal: System is self-sustaining, DR-proven, and enterprise-ready

---

## Phase 16 — Knowledge Lake Real Embeddings and Auto-Update
**Duration:** 7–10 days
**Entry state:** Knowledge Lake uses hash-based vectors (Phase 8 stub); no auto-update
**Exit state:** Real semantic embeddings; IS Agent continuously updates documentation

### What to do

**1. Add real embedding generation**

Replace hash-based `_vector_for_content()` in `qdrant_store.py` with a real
embedding call. Options:
- OpenAI `text-embedding-3-small` (1536-dim, fast, cheap)
- Gemini `text-embedding-004` (768-dim)
- Local model via `sentence-transformers` for full local-first operation

Update `QDRANT_VECTOR_SIZE` in settings accordingly.

**2. Implement IS Agent continuous indexing loop**

Create a background task in the orchestrator that:
- Checks for language version updates (Python, JS, etc.) weekly
- Crawls official documentation for changed pages
- Re-indexes changed content
- Broadcasts Protocol Sigma `DOCUMENTATION_UPDATED` events

**3. Pre-populate Knowledge Lake on first boot**

Add a `make knowledge-init` target that downloads and indexes a baseline
documentation set for all 20 supported languages before the first mission runs.

---

## Phase 17 — DR Evidence, Git History Scrub, and Release Hardening
**Duration:** 3–5 days
**Entry state:** DR scripts exist but no timed drill evidence; TLS keys in git history
**Exit state:** DR drill is documented; git history is clean; promotion gate passes

### What to do

**1. Execute and document DR drill**

```bash
make backup         # Take a full PostgreSQL backup
# Kill orchestrator
# Restore from backup
make dr             # Run dr_drill.ps1 which measures RTO
```

Record: backup timestamp, restore timestamp, RTO in seconds, data verified.
Store in `docs/evidence/dr_drill_2026.json`.

**2. Scrub git history**

```bash
pip install git-filter-repo
git filter-repo --path deploy/postgres/certs/server.key --invert-paths
git filter-repo --path deploy/redis/certs/redis.key --invert-paths
# Force push to all remotes
git push --force --all
```

Rotate the actual certificates (generate fresh ones via `make tls-certs`).

**3. Update promotion policy to reflect DR evidence**

Add `dr_evidence_verified` to the qualification gates in `promotion-policy.json`.

---

## Phase 18 — End-to-End Demo Missions and Production Launch
**Duration:** 5–7 days
**Entry state:** System works but has no curated demo missions proving value
**Exit state:** 3 reproducible demo missions prove the system works for real use cases; documentation is current; system is launch-ready

### What to do

**1. Build and validate 3 canonical demo missions**

**Demo 1 — BUILD_NEW (Simple):**
Prompt: "Write a Python command-line tool that counts word frequency in a text file"
Expected: Working Python script with argparse, file I/O, Counter logic

**Demo 2 — ANALYZE_ONLY (Medium):**
Prompt: Submit the HGR `concept_catalog.py` itself for analysis
Expected: AIM showing domain distribution, function graph, recommendations

**Demo 3 — IMPORT_MODERNIZE (Complex):**
Prompt: Submit a simple legacy Python 2-style script for modernization to Python 3
Expected: Modernized Python 3 output with type hints and f-strings

**2. Create reproducible demo test**

Add `tests/services/test_demo_missions.py`:
```python
@pytest.mark.demo
def test_build_new_wordcount_demo():
    """Canonical demo: BUILD_NEW Python word counter."""
```

Add `make demo` to Makefile that runs these tests against a live stack.

**3. Update all documentation to reflect current state**

- `README.md` — update with current feature list, demo instructions
- `docs/IMPLEMENTATION_STATUS.md` — mark all Tier 1–5 phases complete
- `docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md` — update scope boundaries
- `docs/00_PRODUCT_OVERVIEW.md` — add live demo section

**4. Final promotion gate validation**

```bash
make promotion-gate
# Must pass all qualification gates including:
# - CI green
# - DR evidence present
# - Model governance clean
# - Canary trend passing
# - Mission artifact qualification passing
```

---

# Summary Table

| Phase | Name | Tier | Duration | Key Output |
|-------|------|------|----------|------------|
| 1 | Fix Model Layer | 1 | 1–2 days | Real LLM calls succeed |
| 2 | CEO Refined-IR Contract | 1 | 3–5 days | CEO produces what to build |
| 3 | Specialist Code Generation | 1 | 5–7 days | **System produces software** |
| 4 | PM Feature Contract | 2 | 3–5 days | Structured intake |
| 5 | CEO Logic Clusters | 2 | 3–4 days | CEO decomposes missions |
| 6 | Sub-Manager Consolidation | 2 | 4–5 days | Cross-language dedup |
| 7 | Java + JS AST Extractors | 2 | 2–3 days | Wave 1 AST complete |
| 8 | FETCH / Knowledge Lake | 3 | 7–10 days | Documentation context |
| 9 | FUSION / Master Logic Stream | 3 | 5–7 days | Cross-pod synthesis |
| 10 | DELIVERY / PM Verification | 3 | 4–5 days | Clear output presentation |
| 11 | Application Intelligence Map | 3 | 5–7 days | Pre-analysis for repo missions |
| 12 | Equivalence Verification | 4 | 7–10 days | 0.0001% tolerance gate |
| 13 | Compliance + Security Agents | 4 | 5–7 days | IP and vulnerability checks |
| 14 | Dependency Absorption (DEPABS) | 4 | 10–14 days | Eliminate dependencies |
| 15 | Accountant / Token Ledger | 4 | 2–3 days | Per-mission cost tracking |
| 16 | Knowledge Lake Real Embeddings | 5 | 7–10 days | Semantic documentation search |
| 17 | DR Evidence + Git Scrub | 5 | 3–5 days | Production-clean repo |
| 18 | Demo Missions + Launch | 5 | 5–7 days | Reproducible demos, launch-ready |

**Total estimated duration:** 82–120 days (11–17 weeks) working with Claude Code / Codex

---

# Critical Path

The critical path — the sequence where each phase depends on the previous —
runs through Phases 1 → 2 → 3 → 9 → 10. Everything else can be developed
in parallel or in any order within its tier.

Phases 4, 5, 6, 7, 8, 11 can run in parallel with each other after Phase 3 completes.
Phases 12, 13, 14, 15 can run in parallel with each other after Phase 11 completes.
Phases 16, 17 can run in parallel before Phase 18.

The minimum path to a working demo is:
**Phase 1 → Phase 2 → Phase 3** (9–14 days total)

---

# Rules for Each Phase

1. **Read `AGENTS.md` before touching any file.** When docs and code disagree, code is truth.
2. **No phase is complete until `make test` passes green.**
3. **No phase is complete until `make validate` passes green.**
4. **Every new code path has at least one unit test.**
5. **Every LLM-calling code path has a deterministic fallback.**
6. **Every phase updates `IMPLEMENTATION_STATUS.md` and `ROADMAP.md`.**
7. **Run `python scripts/production_review_audit.py` at end of each phase.**
8. **Never remove existing tests. New intelligence must not regress existing behavior.**
