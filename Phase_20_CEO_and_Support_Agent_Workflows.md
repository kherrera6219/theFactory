# Phase 20 — CEO and Support Agent Workflow Depth

**Status:** CEO continuity and HW context implemented; LLM support-agent activation remains gated
**Last updated:** 2026-05-19
**Depends on:** Phase 19 core system prompts and risk propagation

---

## Problem

### CEO Agent (AGENT-02-CEO)

The CEO makes three sequential LLM calls during a mission:

1. `generate_ceo_delegation` — picks pod manager and specialist
2. `generate_mission_contract` — produces the durable contract
3. `generate_logic_clusters` — decomposes into domain clusters

Each call is independent. Call 2 receives a JSON dump of call 1's output as
context. Call 3 receives a JSON dump of call 2's output. There is no reasoning
continuity — the CEO does not reason about *why* it chose the pod manager it
did when writing the contract, and does not reflect on the contract's risk
surface when decomposing clusters.

Specific gaps:
- `_build_prompt()` (delegation) is 5 lines with no strategic framing.
- `_build_logic_clusters_prompt()` does not ask the CEO to reason about
  workload balance, parallelism, or dependency ordering between clusters.
- The CEO never flags missions that appear underspecified, multi-language,
  or cross-pod. It always produces output regardless of complexity signals.
- Mission type routing is implicit — a `DEBUG_REPAIR` and a `BUILD_NEW` get
  structurally identical CEO workflows.
- The CEO's three calls produce no shared reasoning trace visible in chain
  trace. Each is a black box.

### Support Ring (AGENTS 03–11, 39–41)

The Support Ring has 14 agents. Their actual runtime status by category:

| Agent | Current State |
|---|---|
| AGENT-03-BROKER | Synthesized heartbeat — no real LLM call, no routing logic |
| AGENT-04-ACCOUNTANT | Phase 15 adds token ledger — still no mission-level advisory |
| AGENT-05-SECURITY | Pattern-based scan in `security_compliance.py` — no LLM, no threat reasoning |
| AGENT-06-IS | Static bootstrap docs in `is_agent.py` — Phase 16 adds crawling |
| AGENT-07-VC | Synthesized heartbeat — no commit hygiene, no rollback assessment |
| AGENT-08-COMPLIANCE | Hard-coded license map in `security_compliance.py` — no LLM reasoning |
| AGENT-09-HW | Synthesized heartbeat — no hardware context injected into any prompt |
| AGENT-10-TESTER | Synthesized heartbeat — no integration test generation |
| AGENT-11-DEPLOY | Synthesized heartbeat — no packaging readiness assessment |
| AGENT-39-DEPABS | Advisory absorption plans in Phase 14 — no rewrite generation |
| AGENT-40-TESTDATA | Synthesized heartbeat — not implemented |
| AGENT-41-RQCA | Synthesized heartbeat — not implemented |

The pattern is: most support agents produce synthesized heartbeats and contribute
nothing to mission quality. The few that do run (Security, Compliance, DEPABS)
use regex/heuristics, not LLM reasoning. The agent model matrix assigns
high-capability models to these agents (Claude Opus 4.7 for Security,
Compliance, Tester; Gemini 3.1 Pro for IS, HW) but those models are never called.

This phase activates the CEO's reasoning continuity and the highest-value
support agents — those whose output can directly improve mission quality or
catch failures before delivery.

---

## Implementation Update — 2026-05-19

Completed in this pass:

- Replaced the minimal CEO delegation prompt with mission-type-aware strategic
  guidance for BUILD_NEW, DEBUG_REPAIR, SECURITY_HARDEN, PORT,
  REDUCE_DEPENDENCIES, IMPORT_MODERNIZE, and ANALYZE_ONLY.
- Carried CEO delegation rationale into the mission-contract prompt.
- Added workload-balance and dependency-ordering guidance to logic-cluster
  decomposition prompts.
- Added `depends_on` to normalized logic cluster records.
- Added `CEO_REASONING_SUMMARY` chain-trace event with delegation rationale,
  contract summary, cluster count, cross-pod flags, and support-agent flags.
- Added deterministic `hw_agent.py` hardware context injection for
  performance-sensitive systems-language/codegen prompts.
- Added focused regression coverage in `tests/services/test_llm_delegation_unit.py`.

Deferred from this pass:

- LLM-backed Security, VC, Tester, and Compliance support-agent workflows.
- Mission Control panels for commit strategy and generated tests.
- Integration-test artifact packaging. These require broader delivery-flow and
  UI changes and should remain feature-flagged when implemented.

---

## Goals

1. Give the CEO a coherent reasoning thread across all three calls: delegation
   rationale informs contract shape; contract risk surface informs cluster
   decomposition strategy.
2. Add mission-type-aware CEO behavior so `DEBUG_REPAIR`, `SECURITY_HARDEN`,
   `PORT`, and `REDUCE_DEPENDENCIES` missions get strategically different
   contracts and cluster decompositions from `BUILD_NEW`.
3. Activate four high-value support agents with real LLM-backed workflows:
   Security (LLM threat analysis), VC (commit strategy and rollback plan),
   HW (hardware context injection), and Tester (integration test generation).
4. Upgrade the Compliance and DEPABS agents from regex/heuristics to
   LLM-assisted reasoning for ambiguous cases.
5. Keep all changes behind feature flags with deterministic fallbacks. No
   existing mission flow is broken.

---

## Change 1 — CEO reasoning continuity

### 1a. Delegation prompt — strategic framing by mission type

Replace `_build_prompt()` with a mission-type-aware version:

```python
def _build_ceo_delegation_prompt(
    *,
    mission_context: dict[str, Any],
    recommended_provider: str,
    recommended_model: str,
) -> str:
    mission_type = str(
        mission_context.get("mission_type") or "BUILD_NEW"
    ).strip().upper()
    language = str(
        mission_context.get("requested_target_language") or "auto"
    ).strip().lower()
    feature_contract = mission_context.get("feature_contract") or {}
    complexity = str(
        feature_contract.get("estimated_complexity") or "medium"
    ).strip().lower()

    # Mission-type strategic guidance injected into the delegation decision
    _TYPE_STRATEGY = {
        "BUILD_NEW": (
            "Select the pod whose language specialist has the strongest code generation "
            "capability for the requested language. Prefer specialists with high codegen "
            "confidence."
        ),
        "DEBUG_REPAIR": (
            "Select the pod whose specialist has the deepest static analysis and "
            "fault-isolation capability for the source language. Prioritize audit "
            "confidence over generation speed."
        ),
        "SECURITY_HARDEN": (
            "Select the pod whose specialist understands security-sensitive patterns "
            "for the source language. Flag that Security and Compliance agents must "
            "both run before COMPLETE."
        ),
        "PORT": (
            "Two languages are involved. Select the source-language specialist to "
            "extract intent and the target-language pod manager for generation. "
            "Note the cross-pod dependency in your rationale."
        ),
        "REDUCE_DEPENDENCIES": (
            "Select the pod whose specialist can identify import-level intent and "
            "generate replacement code. DEPABS agent must run. Flag absorption "
            "candidates in your rationale."
        ),
        "IMPORT_MODERNIZE": (
            "Select the pod whose specialist understands the legacy patterns in the "
            "source language. Modernization requires both extraction and generation."
        ),
        "ANALYZE_ONLY": (
            "Select the pod whose specialist can produce the richest LogicNode "
            "coverage for the source language. No code generation required."
        ),
    }
    strategy = _TYPE_STRATEGY.get(mission_type, _TYPE_STRATEGY["BUILD_NEW"])
    complexity_note = (
        " This is a high-complexity mission — consider whether multiple clusters "
        "and parallel pod assignments are warranted."
        if complexity in {"high", "very_high"}
        else ""
    )

    return (
        "You are AGENT-02-CEO in a strict chain-of-command runtime.\n"
        f"Recommended model route: {recommended_provider}/{recommended_model}\n"
        "Return only JSON with keys: pod_manager_agent_id, specialist_agent_id, rationale.\n\n"
        f"Mission type: {mission_type}\n"
        f"Target language: {language}\n"
        f"Strategic guidance: {strategy}{complexity_note}\n\n"
        "Valid pod manager ids:\n"
        "  AGENT-12-PODA-MGR (Pod A: Python, JS/TS, Ruby, PHP)\n"
        "  AGENT-18-PODB-MGR (Pod B: C, C++, Rust, Go, Zig)\n"
        "  AGENT-24-PODC-MGR (Pod C: Java, C#, Scala, Kotlin)\n"
        "  AGENT-30-PODD-MGR (Pod D: R, MATLAB, Julia, Haskell, OCaml)\n\n"
        "Your rationale must explain: why this pod, why this specialist, "
        "and any cross-pod or support-agent dependencies flagged by mission type.\n\n"
        f"Mission context JSON:\n{_safe_context_json(mission_context)}"
    )
```

### 1b. Mission contract prompt — carry delegation rationale forward

In `_build_mission_contract_prompt()`, add the delegation rationale explicitly:

```python
delegation_rationale = _clean_text(
    ceo_delegation.get("rationale", ""), max_length=280
)
rationale_block = (
    f"CEO delegation rationale: {delegation_rationale}\n"
    if delegation_rationale
    else ""
)
# Insert rationale_block into the prompt before the JSON schema block
```

This means the model writing the contract already knows *why* the CEO chose
the pod it did, and can reflect that in risk_notes and acceptance_criteria.

### 1c. Logic clusters prompt — decompose with balance awareness

Extend `_build_logic_clusters_prompt()` with workload balance guidance:

```python
cluster_guidance = (
    "Decompose into 1–8 clusters. Rules:\n"
    "  - Each cluster must be ownable by a single pod manager.\n"
    "  - Clusters that can run in parallel should be at the same priority level.\n"
    "  - Clusters with dependencies on other clusters must be at lower priority.\n"
    "  - For DEBUG_REPAIR missions: one cluster per suspected fault domain.\n"
    "  - For PORT missions: extraction cluster (source pod) and "
    "generation cluster (target pod) are always separate.\n"
    "  - For SECURITY_HARDEN: one cluster must be tagged domain='security_audit'.\n"
    "  - For REDUCE_DEPENDENCIES: one cluster must be tagged domain='dependency_absorption'.\n"
    "Include a 'depends_on' field (list of cluster titles) for ordering when relevant.\n"
)
```

Add `depends_on` to the cluster schema in `_normalize_logic_clusters()`.

### 1d. CEO reasoning summary in chain trace

After all three CEO calls complete in `mission_flow_v2.py`, emit a
`CEO_REASONING_SUMMARY` chain event:

```python
append_chain_event(
    metadata,
    event_type="CEO_REASONING_SUMMARY",
    agent_id=CEO_AGENT_ID,
    details={
        "delegation_rationale": ceo_delegation.get("rationale"),
        "contract_summary": mission_contract.get("contract_summary"),
        "cluster_count": len(logic_clusters.get("clusters", [])),
        "cross_pod_flags": _extract_cross_pod_flags(logic_clusters),
        "support_agent_flags": _extract_support_agent_flags(
            ceo_delegation, mission_type
        ),
    },
)
```

`_extract_support_agent_flags()` reads the CEO delegation rationale for
keywords like "Security", "DEPABS", "Compliance" and returns a list of
support agent IDs the CEO flagged as required. These flags are passed into
metadata so the mission flow can check them against which support agents
actually ran.

---

## Change 2 — Security Agent: LLM threat analysis

`AGENT-05-SECURITY` currently runs pattern matching only. Add an LLM
reasoning pass for missions where generated code is present and patterns
fire, using the Security agent's assigned model (claude-opus-4-7).

### 2a. Add `generate_security_threat_analysis()` to `llm_delegation.py`

```python
async def generate_security_threat_analysis(
    *,
    mission_id: str,
    generated_code: str,
    pattern_findings: list[dict[str, Any]],
    language: str,
    mission_type: str,
) -> dict[str, Any]:
    """
    LLM-backed threat analysis when pattern scan finds potential issues.
    Only called when SECURITY_LLM_ANALYSIS_ENABLED=true and patterns fired.
    """
    recommendation = _agent_recommendation("AGENT-05-SECURITY")
    findings_text = "\n".join(
        f"- {f.get('type', 'unknown')}: {f.get('description', '')}"
        for f in pattern_findings[:10]
    )
    prompt = (
        "You are AGENT-05-SECURITY. Pattern scanning found potential issues in "
        "generated code. Reason about actual exploitability and severity.\n"
        "Return only JSON. No markdown.\n\n"
        f"Language: {language}\n"
        f"Mission type: {mission_type}\n"
        f"Pattern findings:\n{findings_text}\n\n"
        f"Code excerpt (first 1500 chars):\n"
        f"{_clean_text(generated_code[:1500], max_length=1500)}\n\n"
        "Required JSON:\n"
        "{\n"
        '  "threat_level": "CRITICAL | HIGH | MEDIUM | LOW | INFORMATIONAL",\n'
        '  "exploitable": true,\n'
        '  "exploit_scenario": "one sentence describing realistic attack path or null",\n'
        '  "false_positive_likely": false,\n'
        '  "remediation": "specific fix recommendation",\n'
        '  "block_delivery": true\n'
        "}\n"
    )
    system = _system_prompt_for_agent("AGENT-05-SECURITY")
    parsed, provider, model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"security threat analysis {mission_id}",
        system_prompt=system,
    )
    if not isinstance(parsed, dict):
        return {
            "threat_level": "UNKNOWN",
            "exploitable": None,
            "false_positive_likely": True,
            "source": "fallback",
        }
    return {**parsed, "source": "llm", "model_provider": provider, "model": model}
```

### 2b. Wire into `build_security_compliance_report()`

After the existing pattern scan in `security_compliance.py`, if pattern
findings are non-empty and `SECURITY_LLM_ANALYSIS_ENABLED=true`:

```python
if enforcement_enabled and code_findings and llm_analysis_enabled:
    threat_analysis = await generate_security_threat_analysis(
        mission_id=mission_id,
        generated_code=code,
        pattern_findings=code_findings,
        language=language,
        mission_type=mission_type,
    )
    # Override block decision with LLM verdict
    if threat_analysis.get("false_positive_likely"):
        # Downgrade to warning — pattern fired but LLM says not exploitable
        should_block = False
        status = "warned"
    report["threat_analysis"] = threat_analysis
```

Add `SECURITY_LLM_ANALYSIS_ENABLED=false` to settings. Default off.

---

## Change 3 — VC Agent: commit strategy and rollback plan

`AGENT-07-VC` is currently a synthesized heartbeat with no LLM work. For
missions that produce a `generated_code` artifact, the VC agent should produce
a commit strategy document: what files changed, suggested commit message,
rollback plan if the artifact is rejected post-delivery.

### 3a. Add `generate_vc_commit_strategy()` to `llm_delegation.py`

```python
async def generate_vc_commit_strategy(
    *,
    mission_id: str,
    mission_contract: dict[str, Any],
    generated_output: dict[str, Any],
    source_bundle_manifest: list[str],
    language: str,
) -> dict[str, Any]:
    """
    VC Agent produces commit strategy and rollback plan for generated artifacts.
    Called during DELIVERY phase when generated_code artifact exists.
    """
    recommendation = _agent_recommendation("AGENT-07-VC")
    filename = str(generated_output.get("filename") or f"output.{language}")
    description = str(generated_output.get("description") or "generated output")
    contract_summary = str(mission_contract.get("contract_summary") or "mission")
    files_modified = source_bundle_manifest[:20] if source_bundle_manifest else [filename]

    prompt = (
        "You are AGENT-07-VC. Produce a commit strategy and rollback plan for "
        "this mission's generated artifact.\n"
        "Return only JSON. No markdown.\n\n"
        f"Mission: {_clean_text(contract_summary, max_length=200)}\n"
        f"Generated file: {filename} ({language})\n"
        f"Artifact description: {_clean_text(description, max_length=140)}\n"
        f"Files in source bundle: {json.dumps(files_modified)}\n\n"
        "Required JSON:\n"
        "{\n"
        '  "suggested_branch": "feature/hgr-mission-<short-slug>",\n'
        '  "commit_message": "conventional commit message (feat/fix/refactor)",\n'
        '  "files_to_stage": ["list of files"],\n'
        '  "rollback_plan": "one sentence — how to revert if this fails in review",\n'
        '  "review_checklist": ["items a human reviewer should verify"],\n'
        '  "risk_level": "LOW | MEDIUM | HIGH"\n'
        "}\n"
    )
    system = _system_prompt_for_agent("AGENT-07-VC")
    parsed, provider, model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"vc commit strategy {mission_id}",
        system_prompt=system,
    )
    if not isinstance(parsed, dict):
        return {
            "suggested_branch": f"feature/hgr-{mission_id[:8]}",
            "commit_message": f"feat: generated output for mission {mission_id[:8]}",
            "files_to_stage": [filename],
            "rollback_plan": "Revert the generated file to previous version.",
            "review_checklist": ["Verify output satisfies acceptance criteria."],
            "risk_level": "MEDIUM",
            "source": "fallback",
        }
    return {**parsed, "source": "llm", "model_provider": provider, "model": model}
```

### 3b. Wire into DELIVERY phase in `mission_flow_v2.py`

In `_prepare_delivery()`, after build artifact packaging succeeds and
`VC_AGENT_ENABLED=true`:

```python
from .llm_delegation import generate_vc_commit_strategy

if vc_agent_enabled and isinstance(metadata.get("generated_output"), dict):
    source_manifest = _workload_items_from_source_bundle(
        metadata.get("source_code", "")
    )
    vc_strategy = await generate_vc_commit_strategy(
        mission_id=mission_id,
        mission_contract=metadata.get("mission_contract", {}),
        generated_output=metadata["generated_output"],
        source_bundle_manifest=source_manifest,
        language=mission.requested_target_language or "unknown",
    )
    metadata["vc_commit_strategy"] = vc_strategy
    append_chain_event(
        metadata,
        event_type="MISSION_VC_STRATEGY_PRODUCED",
        agent_id="AGENT-07-VC",
        details={
            "risk_level": vc_strategy.get("risk_level"),
            "suggested_branch": vc_strategy.get("suggested_branch"),
            "source": vc_strategy.get("source"),
        },
    )
```

Expose `vc_commit_strategy` in chain trace. Render in Mission Detail as a
collapsible "Commit Strategy" panel with branch name, commit message, rollback
plan, and review checklist.

Add `VC_AGENT_ENABLED=false` to settings. Default off.

---

## Change 4 — HW Agent: hardware context injection

`AGENT-09-HW` is a synthesized heartbeat today. Its actual value is narrow but
real: it knows the runtime hardware (AW1: i7-14700F, RTX 4060 Ti, 64GB RAM)
and should inject relevant constraints into specialist prompts for
performance-sensitive missions.

This is not a full LLM call — it is a deterministic context block injected
into the specialist code-generation prompt for missions where hardware
characteristics matter.

### 4a. Add `build_hw_context_block()` to a new `hw_agent.py`

```python
"""hw_agent.py — Hardware context injection for performance-sensitive missions."""
from __future__ import annotations
from typing import Any

# AW1 hardware profile — update when hardware changes
_AW1_PROFILE = {
    "cpu": "Intel i7-14700F (20 cores, 28 threads, 5.4GHz boost)",
    "gpu": "NVIDIA RTX 4060 Ti (8GB VRAM, CUDA 12.x)",
    "ram": "64GB DDR5",
    "storage": "1TB NVMe SSD",
    "os": "Windows 11 / WSL2",
    "llm_inference": "off-device via API (no local GPU inference)",
}

_PERFORMANCE_SENSITIVE_TYPES = {
    "BUILD_NEW", "PORT", "IMPORT_MODERNIZE", "REDUCE_DEPENDENCIES",
}
_PERFORMANCE_SENSITIVE_DOMAINS = {
    "numerical_computation", "matrix_operations", "parallel_processing",
    "gpu_acceleration", "memory_management", "io_operations",
    "system_calls", "crypto",
}


def build_hw_context_block(
    *,
    mission_type: str,
    language: str,
    logic_clusters: dict[str, Any] | None,
) -> str:
    """
    Return a hardware context string for injection into specialist prompts.
    Returns empty string when hardware context is not relevant.
    """
    if mission_type.upper() not in _PERFORMANCE_SENSITIVE_TYPES:
        return ""

    # Check if any cluster domain is performance-sensitive
    clusters = (logic_clusters or {}).get("clusters") or []
    cluster_domains = {
        str(c.get("domain") or "").lower() for c in clusters
    }
    has_perf_domain = bool(
        cluster_domains & _PERFORMANCE_SENSITIVE_DOMAINS
    )

    # Always inject for systems languages regardless of domain
    is_systems_language = language.lower() in {
        "c", "cpp", "rust", "go", "zig", "julia", "matlab"
    }

    if not (has_perf_domain or is_systems_language):
        return ""

    return (
        f"\nRuntime hardware context (AW1):\n"
        f"  CPU: {_AW1_PROFILE['cpu']}\n"
        f"  GPU: {_AW1_PROFILE['gpu']} — available for CUDA/compute workloads\n"
        f"  RAM: {_AW1_PROFILE['ram']} — large working set is available\n"
        f"  LLM inference: {_AW1_PROFILE['llm_inference']}\n"
        "  Optimize generated code for this hardware profile when relevant.\n"
        "  Avoid assuming constrained memory or single-core execution.\n"
    )
```

### 4b. Inject into `_build_codegen_prompt()`

```python
from .hw_agent import build_hw_context_block

hw_context = build_hw_context_block(
    mission_type=str(mission_context.get("mission_type") or "BUILD_NEW"),
    language=target_language,
    logic_clusters=mission_context.get("logic_clusters"),
)
# Append hw_context before the JSON instruction block
```

No LLM call — pure deterministic injection. Zero cost, always-on when relevant.
Remove the `HW_AGENT_ENABLED` flag consideration — this is safe to run always.

---

## Change 5 — Tester Agent: integration test generation

`AGENT-10-TESTER` is currently a synthesized heartbeat. For `BUILD_NEW` and
`PORT` missions that produce `generated_code`, the Tester agent should produce
an integration test file alongside the generated output.

### 5a. Add `generate_integration_tests()` to `llm_delegation.py`

```python
async def generate_integration_tests(
    *,
    mission_id: str,
    generated_output: dict[str, Any],
    mission_contract: dict[str, Any],
    feature_contract: dict[str, Any],
    language: str,
) -> dict[str, Any]:
    """
    Tester Agent generates an integration test file for the generated output.
    Called during DELIVERY phase when TESTER_AGENT_ENABLED=true.
    """
    recommendation = _agent_recommendation("AGENT-10-TESTER")
    code = str(generated_output.get("generated_code") or "")[:2000]
    filename = str(generated_output.get("filename") or f"output.{language}")
    contract_summary = str(mission_contract.get("contract_summary") or "mission")
    acceptance = "\n".join(
        f"- {_clean_text(item, max_length=140)}"
        for item in (
            feature_contract.get("acceptance_criteria")
            or mission_contract.get("acceptance_criteria")
            or []
        )[:6]
    ) or "- Verify output satisfies the mission contract."

    prompt = (
        "You are AGENT-10-TESTER. Generate an integration test file for the "
        "provided generated code. Tests must be runnable without mocking the "
        "entire system — test the generated code's exported interface directly.\n"
        "Return only JSON. No markdown.\n\n"
        f"Language: {language}\n"
        f"Generated file: {filename}\n"
        f"Mission: {_clean_text(contract_summary, max_length=200)}\n"
        f"Acceptance criteria:\n{acceptance}\n\n"
        f"Generated code:\n{_clean_text(code, max_length=2000)}\n\n"
        "Required JSON:\n"
        "{\n"
        '  "test_code": "complete test file source",\n'
        '  "test_filename": "test_<filename> or <filename>.test.js",\n'
        '  "test_framework": "pytest | jest | junit | go test | etc",\n'
        '  "test_count": 3,\n'
        '  "covers_acceptance_criteria": ["criterion text covered by tests"],\n'
        '  "manual_review_items": ["items that cannot be automatically tested"]\n'
        "}\n"
    )
    system = _system_prompt_for_agent("AGENT-10-TESTER")
    parsed, provider, model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"tester integration tests {mission_id}",
        system_prompt=system,
    )
    if not isinstance(parsed, dict):
        return {"source": "fallback", "test_code": "", "test_count": 0}
    return {
        **parsed,
        "source": "llm",
        "model_provider": provider,
        "model": model,
        "generated_at": datetime.now(UTC).isoformat(),
    }
```

### 5b. Wire into DELIVERY phase

In `_prepare_delivery()`, after `generate_vc_commit_strategy`, when
`TESTER_AGENT_ENABLED=true` and mission type is in
`{"BUILD_NEW", "PORT", "IMPORT_MODERNIZE"}`:

```python
test_output = await generate_integration_tests(
    mission_id=mission_id,
    generated_output=metadata["generated_output"],
    mission_contract=metadata.get("mission_contract", {}),
    feature_contract=metadata.get("feature_contract", {}),
    language=mission.requested_target_language or "python",
)
metadata["integration_tests"] = test_output
append_chain_event(
    metadata,
    event_type="MISSION_TESTS_GENERATED",
    agent_id="AGENT-10-TESTER",
    details={
        "test_count": test_output.get("test_count", 0),
        "test_framework": test_output.get("test_framework"),
        "source": test_output.get("source"),
    },
)
```

Package the test file alongside the generated code artifact when
`test_output["test_code"]` is non-empty. Store as a second build artifact
with `artifact_type="integration_tests"`.

Render in Mission Control Mission Detail as a "Generated Tests" panel showing
test count, framework, acceptance coverage, and a download button for the test
file.

Add `TESTER_AGENT_ENABLED=false` to settings. Default off.

---

## Change 6 — Compliance Agent: LLM reasoning for ambiguous licenses

The current compliance check in `security_compliance.py` uses a hard-coded
`_LIBRARY_LICENSE_MAP` with ~20 entries. Everything not in the map gets
`"UNKNOWN"` and is flagged as a warning. This produces noisy, low-signal
warnings for common unlisted libraries.

### 6a. Add `generate_compliance_assessment()` to `llm_delegation.py`

```python
async def generate_compliance_assessment(
    *,
    mission_id: str,
    unknown_dependencies: list[str],
    language: str,
    mission_type: str,
) -> dict[str, Any]:
    """
    Compliance Agent reasons about license risk for dependencies not in the
    hard-coded map. Called when COMPLIANCE_LLM_ENABLED=true and unknowns exist.
    """
    recommendation = _agent_recommendation("AGENT-08-COMPLIANCE")
    deps_text = ", ".join(unknown_dependencies[:15])
    prompt = (
        "You are AGENT-08-COMPLIANCE. Assess the license risk of these "
        "third-party dependencies based on your knowledge of common package "
        "ecosystems.\n"
        "Return only JSON. No markdown.\n\n"
        f"Language/ecosystem: {language}\n"
        f"Dependencies to assess: {deps_text}\n\n"
        "For each dependency provide:\n"
        "{\n"
        '  "assessments": [\n'
        '    {\n'
        '      "package": "name",\n'
        '      "likely_license": "MIT | Apache-2.0 | GPL-3.0 | BSD-3-Clause | UNKNOWN",\n'
        '      "risk_level": "LOW | MEDIUM | HIGH",\n'
        '      "risk_reason": "one sentence or null",\n'
        '      "confidence": "HIGH | MEDIUM | LOW"\n'
        '    }\n'
        '  ]\n'
        "}\n"
        "Only flag HIGH risk for strong copyleft (GPL, AGPL) or unknown closed-source.\n"
    )
    system = _system_prompt_for_agent("AGENT-08-COMPLIANCE")
    parsed, provider, model, route = await _call_with_recommendation(
        recommendation=recommendation,
        prompt=prompt,
        call_context=f"compliance assessment {mission_id}",
        system_prompt=system,
    )
    if not isinstance(parsed, dict):
        return {"assessments": [], "source": "fallback"}
    return {
        **parsed,
        "source": "llm",
        "model_provider": provider,
        "model": model,
    }
```

Wire into `build_security_compliance_report()` when `COMPLIANCE_LLM_ENABLED=true`
and the dependency inventory contains packages with `UNKNOWN` license status.
Use LLM assessment to replace `UNKNOWN/warned` verdicts where LLM confidence
is `HIGH` and risk is `LOW` or `MEDIUM` — reducing false-positive noise.

Add `COMPLIANCE_LLM_ENABLED=false` to settings. Default off.

---

## Settings

Add to `settings.py` and `.env.example`:

```bash
# Phase 20 — CEO and Support Agent Workflows
SECURITY_LLM_ANALYSIS_ENABLED=false   # LLM threat reasoning on top of pattern scan
VC_AGENT_ENABLED=false                 # VC commit strategy and rollback plan
TESTER_AGENT_ENABLED=false             # Integration test generation
COMPLIANCE_LLM_ENABLED=false           # LLM license assessment for unknown packages
# HW context injection is always-on when relevant (no flag needed)
```

---

## Non-Goals

- Do not activate BROKER, DEPLOY, TESTDATA, or RQCA in this phase. Those
  require infrastructure integration (real API routing, packaging pipelines,
  ephemeral environments, browser automation) that belongs to a later phase.
- Do not implement multi-agent coordination between support agents. Each
  support agent in this phase produces its own independent artifact. Cross-agent
  reasoning chains are a future phase.
- Do not implement the CEO overriding a support agent verdict. The CEO flags
  support agent requirements; this phase does not implement the enforcement loop.
- Do not store test execution results — Phase 20 generates test files only.
  Execution is a Runtime QC concern (AGENT-41-RQCA, later phase).

---

## Validation

### CEO reasoning continuity
- [x] `BUILD_NEW` delegation prompt contains "code generation capability" strategy text.
- [x] `DEBUG_REPAIR` delegation prompt contains "static analysis and fault-isolation" text.
- [x] `PORT` delegation prompt contains "cross-pod dependency" language.
- [x] Mission contract prompt includes CEO delegation rationale text.
- [ ] Logic clusters for `SECURITY_HARDEN` include a `domain='security_audit'` cluster.
- [x] Logic clusters schema accepts `depends_on` field without validation error.
- [x] Chain trace includes `CEO_REASONING_SUMMARY` event after CEO phase.

### Security LLM analysis
- [ ] With `SECURITY_LLM_ANALYSIS_ENABLED=false`: pattern scan behavior unchanged.
- [ ] With flag enabled and pattern findings: `threat_analysis` present in report.
- [ ] LLM returning `false_positive_likely=true` downgrades block to warn.
- [ ] LLM call failure falls back gracefully without blocking mission.

### VC Agent
- [ ] With `VC_AGENT_ENABLED=false`: no VC call, no metadata key added.
- [ ] With flag enabled and `generated_output` present: `vc_commit_strategy`
      in chain trace with `suggested_branch`, `commit_message`, `rollback_plan`.
- [ ] `MISSION_VC_STRATEGY_PRODUCED` event in chain trace.
- [ ] Mission Control renders Commit Strategy panel when data present.

### HW context injection
- [x] Rust codegen prompt for `BUILD_NEW` contains AW1 CPU/GPU text.
- [x] Python codegen prompt for `ANALYZE_ONLY` does NOT contain HW context.
- [x] JavaScript codegen prompt for `BUILD_NEW` does NOT contain HW context
      (not a systems language, no perf-sensitive domain).
- [x] Julia codegen prompt for `BUILD_NEW` DOES contain HW context
      (systems language).

### Tester Agent
- [ ] With `TESTER_AGENT_ENABLED=false`: no tester call, no metadata key.
- [ ] With flag enabled and `BUILD_NEW` + `generated_output`: `integration_tests`
      in chain trace with `test_count > 0` and non-empty `test_code`.
- [ ] `MISSION_TESTS_GENERATED` event in chain trace.
- [ ] `ANALYZE_ONLY` mission does NOT trigger test generation.
- [ ] Mission Control renders Generated Tests panel when data present.
- [ ] Test file packaged as second build artifact with `artifact_type="integration_tests"`.

### Compliance LLM
- [ ] With `COMPLIANCE_LLM_ENABLED=false`: existing compliance behavior unchanged.
- [ ] With flag enabled and unknown dependencies: `compliance_assessment` present.
- [ ] LLM returning `LOW` risk and `HIGH` confidence for a package removes its
      warning from the compliance report.
- [ ] LLM call failure falls back to existing `UNKNOWN/warned` behavior.

### Full suite
- [ ] `python -m pytest -q` passes on all touched files.
- [ ] `python -m ruff check services/orchestrator tests/services` passes.
- [ ] `npm --prefix apps/mission-control run lint` passes.
- [ ] `npm --prefix apps/mission-control run test` passes.
- [ ] All new support agent calls are non-critical path — LLM failure in any
      support agent never transitions a mission to FAILED.
