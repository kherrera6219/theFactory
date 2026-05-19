# Phase 21 — Pod Agent Workflow Depth

**Status:** Planned
**Last updated:** 2026-05-18
**Depends on:** Phase 20 (CEO system prompts and support agent activation)

---

## Problem

### Pod Managers (AGENTS 12, 18, 24, 30)

Each pod manager makes two LLM calls during a mission:

1. `generate_pod_manager_delegation` — picks the specialist
2. `generate_pod_group_standard` — consolidates specialist LogicNodes

**Gaps:**
- `_build_pod_manager_prompt()` is 7 lines with no pod-family awareness.
- All four pod managers get identical prompt structure despite serving
  radically different language families (dynamic vs systems vs enterprise
  vs mathematical).
- Group standard generation has no coverage quality gate. A standard with
  1 LogicNode for a 50-function source file passes identically to 40 nodes.
- Pod managers never flag thin coverage back to the CEO or audit agent.

### Pod Audit Agents (AGENTS 13, 19, 25, 31)

`PodAuditAgent.execute()` checks that LogicNodes have a `node_id` and
`concept`. That is the complete audit logic. The agent model matrix assigns
claude-sonnet-4-6 to Pod A/B/C audit and claude-opus-4-7 to Pod D audit.
None of these models are called. All four audit agents produce synthesized
heartbeats that pass every mission regardless of LogicNode quality.

### Specialist `_extract_logicnodes()` stub

`SpecialistAgent._extract_logicnodes()` in `agent_base.py` returns one
hard-coded stub node regardless of source or language. Unit-level audit
validation is therefore vacuous — one stub node always passes the structural
field check.

### BROKER Agent (AGENT-03)

Synthesized heartbeat. Adaptive routing is hardcoded in
`_call_with_recommendation()`. No provider health tracking exists so there
is no visibility into latency or error patterns across providers.

### DEPLOY Agent (AGENT-11)

Synthesized heartbeat. Should synthesize evidence from equivalence, security,
and integration test artifacts into a packaging readiness assessment for every
completed mission.

### TESTDATA (AGENT-40) and RQCA (AGENT-41)

Fully unimplemented. Require infrastructure not yet available. Deferred.

---

## Goals

1. Pod-family-aware delegation prompts for all four pod managers.
2. Coverage quality gate on group standard generation.
3. Real LLM-backed semantic audit for all four pod audit agents.
4. Source-reflective `_extract_logicnodes()` replacing the single stub.
5. Broker provider health telemetry groundwork (read-only, zero cost).
6. Deploy Agent packaging readiness assessment at COMPLETE.

---

## Change 1 — Pod-family-aware delegation prompts

Add `_POD_MANAGER_STRATEGY` to `llm_delegation.py`:

```python
_POD_MANAGER_STRATEGY: dict[str, dict[str, str]] = {
    "AGENT-12-PODA-MGR": {
        "family": "Pod A — Dynamic Languages",
        "languages": "Python, JavaScript/TypeScript, Ruby, PHP",
        "primary_concern": (
            "Select the specialist with the strongest idiomatic fluency. "
            "Dynamic languages prioritize correctness of control flow, "
            "closures, and duck-typed contracts."
        ),
        "quality_bar": (
            "Produce LogicNodes with explicit domain, concept, and intent "
            "for every function/class boundary. Flag thin coverage "
            "(< 1 node per 5 source lines)."
        ),
    },
    "AGENT-18-PODB-MGR": {
        "family": "Pod B — Systems Languages",
        "languages": "C, C++, Rust, Go, Zig",
        "primary_concern": (
            "Select the specialist with the strongest systems-level analysis. "
            "Memory safety, ownership semantics, and ABI correctness are "
            "the primary extraction targets."
        ),
        "quality_bar": (
            "Capture memory management domains, FFI boundaries, and unsafe "
            "blocks as explicit LogicNodes. Flag missing safety annotations."
        ),
    },
    "AGENT-24-PODC-MGR": {
        "family": "Pod C — Enterprise Languages",
        "languages": "Java, C#, Scala, Kotlin",
        "primary_concern": (
            "Select the specialist with the strongest enterprise pattern "
            "recognition. DI, interface contracts, and layered architecture "
            "are the primary extraction targets."
        ),
        "quality_bar": (
            "Capture service boundaries, interface declarations, and DTOs. "
            "Framework annotations (Spring, .NET DI) must be surfaced."
        ),
    },
    "AGENT-30-PODD-MGR": {
        "family": "Pod D — Mathematical Languages",
        "languages": "R, MATLAB, Julia, Haskell, OCaml, Mathematica",
        "primary_concern": (
            "Select the specialist with the strongest numerical/functional "
            "analysis capability. Algorithm correctness, type-level proofs, "
            "and numerical stability are primary targets."
        ),
        "quality_bar": (
            "Capture mathematical domains (matrix ops, statistical models, "
            "formal proofs). Numerical precision and type constraints must "
            "be preserved in every LogicNode."
        ),
    },
}
```

Replace `_build_pod_manager_prompt()` with
`_build_pod_manager_delegation_prompt()` that pulls from this map, adds
mission-type context, and includes quality bar instruction. The rationale
must explain: why this specialist for this mission type, and any coverage
risks the specialist should anticipate.

---

## Change 2 — Coverage quality gate in group standard

Add `_pod_standard_coverage_verdict()`:

```python
def _pod_standard_coverage_verdict(
    logicnodes: list[dict],
    canonical_nodes: list[dict],
    source_code: str | None,
) -> dict:
    node_count = len(canonical_nodes)
    raw_count = len(logicnodes)
    source_lines = len((source_code or "").splitlines()) if source_code else 0
    expected_minimum = max(1, source_lines // 20) if source_lines else 1
    thin = node_count < expected_minimum
    dedup_ratio = round(1 - node_count / raw_count, 2) if raw_count > 0 else 0.0
    return {
        "node_count": node_count,
        "raw_node_count": raw_count,
        "estimated_source_lines": source_lines,
        "expected_minimum_nodes": expected_minimum,
        "coverage_thin": thin,
        "deduplication_ratio": dedup_ratio,
        "verdict": "WARN_THIN" if thin else "OK",
    }
```

Attach `coverage_verdict` to the group standard dict. Emit
`MISSION_POD_STANDARD_THIN_COVERAGE` chain event when `coverage_thin=True`.

---

## Change 3 — LLM semantic audit for all four pod audit agents

Add `generate_pod_audit_verdict()` to `llm_delegation.py`.

Inputs: pod name, audit agent ID, up to 12 LogicNodes (prioritizing those
matching contract domains), mission contract, language.

Uses the audit agent's assigned model via `_agent_recommendation()` and
the agent's full persona via `_system_prompt_for_agent()`.

Returns:
- `verdict`: PASS / PARTIAL / FAIL
- `coverage_score`: 0.0–1.0
- `intent_quality_score`: 0.0–1.0
- `findings`: list of specific issue descriptions
- `missing_domains`: domains required by contract but absent in nodes
- `weak_intents`: node IDs whose intent is vague or incomplete
- `blocking`: bool (true only for PRODUCTION depth_mode or SECURITY_HARDEN)
- `summary`: one sentence

Falls back to the structural field check if the LLM call fails.

Wire into `_prepare_gating()` in `mission_flow_v2.py` when
`POD_AUDIT_LLM_ENABLED=true`.

Add `_resolve_audit_agent_for_pod()` helper:
```python
_POD_AUDIT_AGENT_MAP = {
    "AGENT-12-PODA-MGR": "AGENT-13-PODA-AUDIT",
    "AGENT-18-PODB-MGR": "AGENT-19-PODB-AUDIT",
    "AGENT-24-PODC-MGR": "AGENT-25-PODC-AUDIT",
    "AGENT-30-PODD-MGR": "AGENT-31-PODD-AUDIT",
}
```

Render `pod_audit_verdict` in Mission Control as a collapsible "Pod Audit"
panel with verdict chip, coverage score, weak intent list, missing domain list.

Settings: `POD_AUDIT_LLM_ENABLED=false`, `POD_AUDIT_ENFORCEMENT_ENABLED=false`

---

## Change 4 — Specialist stub replacement

Replace `SpecialistAgent._extract_logicnodes()` with a minimal but
source-reflective implementation using per-language regex patterns:

```python
_STUB_PATTERNS = {
    "python":     [r"^\s*def \w+", r"^\s*class \w+"],
    "javascript": [r"\bfunction\s+\w+", r"=>\s*\{", r"^\s*class\s+\w+"],
    "java":       [r"(public|private|protected)\s+\w+\s+\w+\s*\("],
    "rust":       [r"^\s*fn\s+\w+", r"^\s*(pub\s+)?struct\s+\w+"],
    "go":         [r"^\s*func\s+\w+"],
    "cpp":        [r"\w+::\w+\s*\("],
    "c":          [r"^\w[\w\s\*]+\s+\w+\s*\("],
}
```

Produces up to 10 LogicNodes per pattern match. Falls back to one
`source_payload` node only when no patterns match. Empty string returns
empty list.

This is class-level only — the pod-worker's production extractor is unchanged.

---

## Change 5 — Broker provider health telemetry

Add in-process rolling-window health tracking to `llm_delegation.py`:

```python
_provider_call_times: dict[str, list[tuple[float, float]]] = defaultdict(list)
_provider_error_counts: dict[str, int] = defaultdict(int)
_PROVIDER_WINDOW_SECONDS = 300  # 5-minute rolling window
```

Call `_record_provider_call(provider, latency_ms, success)` inside
`_call_provider()` after every attempt.

Expose `get_provider_health_summary()` returning per-provider call count,
avg latency, p95 latency, and total error count.

Add `GET /internal/broker/provider-health` endpoint.

Render a "Provider Health" mini-panel on the agents page for AGENT-03-BROKER
showing live p95 latency and error counts.

**No routing decisions change.** Read-only telemetry only.

---

## Change 6 — Deploy Agent packaging readiness assessment

Add `generate_deploy_readiness()` to `llm_delegation.py`.

Inputs synthesized from existing mission metadata:
- `generated_output` — filename, language, declared dependencies
- `equivalence_report` — passed/not passed/not run
- `security_compliance_report` — status (passed/warned/blocked)
- `integration_tests` — test count

Returns: `readiness` (READY/READY_WITH_WARNINGS/NOT_READY), `confidence`,
`blockers`, `warnings`, `deployment_notes`, `suggested_environment`.

Uses AGENT-11-DEPLOY model (`gemini_ops_balanced`) and persona system prompt.

Wire into the COMPLETE transition in `mission_flow_v2.py` when
`DEPLOY_AGENT_ENABLED=true`. Emit `MISSION_DEPLOY_READINESS_ASSESSED` event.

Render in Mission Control as a "Deploy Readiness" panel with color-coded
badge (green/amber/red), deployment notes, and suggested environment.

Setting: `DEPLOY_AGENT_ENABLED=false`

---

## Deferred agents

| Agent | Reason |
|---|---|
| AGENT-40-TESTDATA | Requires ephemeral environment provisioning and isolated DB lifecycle |
| AGENT-41-RQCA | Requires browser automation, sandboxed execution, and session recording |

These are the two remaining fully unimplemented agents and belong in a
dedicated Runtime QC phase.

---

## Settings

```bash
# Phase 21 — Pod Agent Workflow Depth
POD_AUDIT_LLM_ENABLED=false          # LLM semantic audit in GATING phase
POD_AUDIT_ENFORCEMENT_ENABLED=false  # Block missions on pod audit FAIL verdict
DEPLOY_AGENT_ENABLED=false           # Deploy readiness assessment at COMPLETE
# Broker health tracking: always-on (read-only, zero cost)
```

---

## Non-Goals

- Do not implement the Broker making actual routing decisions. Telemetry only.
- Do not implement cross-pod pod manager coordination (PORT handoff between
  pods belongs in a future architecture phase).
- Do not implement the Deploy agent packaging binaries, building Docker images,
  or pushing to registries. Assessment only in this phase.
- Do not implement TESTDATA or RQCA in this phase.

---

## Validation

### Pod manager delegation
- [ ] PODA-MGR prompt contains "Dynamic Languages" and "duck-typed contracts".
- [ ] PODB-MGR prompt contains "Systems Languages" and "memory safety".
- [ ] PODC-MGR prompt contains "Enterprise Languages" and "interface declarations".
- [ ] PODD-MGR prompt contains "Mathematical Languages" and "numerical stability".
- [ ] All four prompts include mission-type context and quality bar instruction.

### Coverage quality gate
- [ ] 0 nodes + 200-line source returns `coverage_thin=True`, `verdict="WARN_THIN"`.
- [ ] 15 nodes + 200-line source returns `coverage_thin=False`, `verdict="OK"`.
- [ ] `MISSION_POD_STANDARD_THIN_COVERAGE` emitted in chain trace when thin.

### Pod audit LLM
- [ ] `POD_AUDIT_LLM_ENABLED=false`: structural check behavior unchanged.
- [ ] Flag enabled: `pod_audit_verdict` in chain trace with `source="llm"`.
- [ ] LLM call failure returns structural fallback verdict without raising.
- [ ] `POD_AUDIT_ENFORCEMENT_ENABLED=false`: FAIL verdict does not block mission.
- [ ] Enforcement + FAIL: mission does not advance to FUSION.
- [ ] `MISSION_POD_AUDIT_COMPLETE` in chain trace for every audited mission.
- [ ] Mission Control renders Pod Audit panel.

### Specialist stub
- [ ] `PythonAgent._extract_logicnodes(id, "def foo(): pass", "python")`
      returns node with `concept != "extracted_intent"`.
- [ ] `RustAgent._extract_logicnodes(id, "fn main() {}", "rust")` returns
      at least 1 node.
- [ ] Empty string source returns `[]` without crash.
- [ ] Unknown language falls back to generic pattern without KeyError.

### Broker health telemetry
- [ ] After 3 LLM calls, `get_provider_health_summary()` returns non-empty dict.
- [ ] `GET /internal/broker/provider-health` returns 200.
- [ ] Call count resets after 5-minute rolling window (mocked time unit test).
- [ ] `_record_provider_call` failure does not raise or affect LLM call result.

### Deploy readiness
- [ ] `DEPLOY_AGENT_ENABLED=false`: no deploy call, no metadata key added.
- [ ] Flag enabled on COMPLETE mission with `generated_output`:
      `deploy_readiness` in chain trace with `readiness` and `confidence`.
- [ ] `MISSION_DEPLOY_READINESS_ASSESSED` event in chain trace.
- [ ] Security verdict `blocked` produces `readiness="NOT_READY"`.
- [ ] LLM failure returns fallback with `readiness="READY_WITH_WARNINGS"`.
- [ ] Mission Control renders Deploy Readiness panel with color-coded badge.

### Full suite
- [ ] `python -m pytest -q` passes on all touched files.
- [ ] `python -m ruff check services/orchestrator services/pod-worker tests/services`
      passes.
- [ ] `npm --prefix apps/mission-control run lint` passes.
- [ ] `npm --prefix apps/mission-control run test` passes.
- [ ] All new agent calls are non-critical path — LLM failure in any agent
      in this phase never transitions a mission to FAILED.
