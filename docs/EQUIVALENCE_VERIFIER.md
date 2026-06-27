# Equivalence Verifier

Last updated: 2026-06-27

Document version: 2026.06.11  
Status: Canonical  
Audience: Developers and QC engineers

## Overview

`equivalence_verifier.py` (14 KB, `services/orchestrator/orchestrator/equivalence_verifier.py`) implements the **Equivalence Verifier**, the semantic and structural comparison engine used during the verification phase of Mission Flow v2. It answers one question: *does the code the pod workers produced satisfy the intent expressed in the mission brief and AIM?*

This is distinct from syntactic testing (which is handled by the RQCA Agent and test runners). The Equivalence Verifier operates at the semantic level — it compares the logical structure of delivered artifacts against the expected structure described in the Application Intelligence Map (AIM).

## Code Location

```
services/orchestrator/orchestrator/equivalence_verifier.py   # 14 KB
```

**Related files:**

| File | Relationship |
|---|---|
| `aim_generator.py` | Produces the AIM that is the verifier's reference baseline |
| `rqca_agent.py` | Runs syntactic QC; the verifier runs after RQCA passes |
| `mission_flow_v2/` | Calls `EquivalenceVerifier.verify()` at Phase 9 (VERIFY) |
| `audit_events.py` | Verifier emits `EQUIVALENCE_CHECK_PASSED` / `EQUIVALENCE_CHECK_FAILED` events |
| `APPLICATION_INTELLIGENCE_MAP.md` | Describes the AIM artifact that is the verifier's input |

## How It Works

The verifier compares two structured representations:

- **Baseline** — the expected structure extracted from the mission AIM (produced by `aim_generator.py`)
- **Candidate** — the structure extracted from the delivered artifacts by static analysis

Comparison is performed across three planes:

| Plane | What is compared | Pass threshold |
|---|---|---|
| **Structural** | Function signatures, class hierarchies, module exports | Exact match on public interface |
| **Semantic** | LogicNode tags present in the baseline vs. detected in the candidate | ≥ 90% recall |
| **Dependency** | Dependency manifest in baseline vs. actual imports in candidate | Exact match (no undeclared deps) |

If all three planes pass, a `EQUIVALENCE_CHECK_PASSED` audit event is emitted and Mission Flow v2 advances to Phase 10 (DELIVER). If any plane fails, a `EQUIVALENCE_CHECK_FAILED` event is emitted with a structured diff, and the mission is routed to the remediation loop.

## Key Dataclasses

```python
@dataclass
class EquivalenceReport:
    mission_id: str
    passed: bool
    structural_score: float       # 0.0–1.0
    semantic_recall: float        # 0.0–1.0
    dependency_match: bool
    structural_diff: list[str]    # list of mismatched signatures
    semantic_diff: list[str]      # list of missing/extra LogicNode tags
    dependency_diff: list[str]    # list of undeclared or missing deps
    duration_ms: int
```

## Remediation Loop

When `EquivalenceReport.passed == False`, Mission Flow v2 enters a bounded remediation loop:

1. The structured diff is passed to the relevant pod worker as a correction brief
2. The pod worker re-generates the failing artifact(s)
3. The Equivalence Verifier re-runs (max 2 remediation attempts)
4. If still failing after 2 attempts, the mission is escalated to `HUMAN_REVIEW` state

## Thresholds and Configuration (`settings.py` keys)

| Key | Default | Description |
|---|---|---|
| `EQUIV_SEMANTIC_RECALL_MIN` | `0.90` | Minimum semantic recall to pass |
| `EQUIV_MAX_REMEDIATION_ATTEMPTS` | `2` | Maximum correction loop iterations |
| `EQUIV_STRUCTURAL_STRICT` | `true` | Whether structural plane requires exact match |

## Operational Notes

- Equivalence reports are stored as mission artifacts and included in the chain-of-custody evidence bundle.
- The verifier does not execute code; it performs static analysis only. Runtime correctness is the domain of the RQCA Agent and the test runners.
- Failures at the dependency plane are the most common cause of remediation loops and are often caused by undeclared stdlib imports in generated code.
