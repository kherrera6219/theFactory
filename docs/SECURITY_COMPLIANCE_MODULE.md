# Security Compliance Module

Document version: 2026.06.13
Last updated: 2026-06-27
Status: Canonical
Audience: Developers and operators

**Source file:** `services/orchestrator/orchestrator/security_compliance.py`  
**Size:** ~11 KB  
**Role:** Runtime enforcement of the security and compliance policy defined in `DATA_CLASSIFICATION_POLICY.md` and `SENSITIVE_CODE_HANDLING_POLICY.md`. Called at mission intake and before LLM delegation for Tier 2/3 missions.

---

## Overview

`security_compliance.py` is the runtime gatekeeper between mission content and the LLM delegation layer. It enforces three things:

1. **Data classification tier checks** — validates that the requested `OutputMode`, `DepthMode`, and target language are permitted for the mission's `DataClassification` tier
2. **Sensitive code detection** — scans mission prompt and attachment content for patterns that indicate regulated or sensitive material (credentials, PII markers, regulated-domain keywords)
3. **`local_only` agent enforcement** — for Tier 3 missions, verifies that only agents with `local_only: true` in their persona are selected for LLM calls; blocks any persona that would route to an external cloud provider

It does not own any storage — all results are written back into `mission.metadata` by the caller and persisted via `storage_missions.update_mission_metadata()`.

---

## When It Is Called

| Trigger | Caller | What it checks |
|---|---|---|
| Mission `PM_INTAKE` | `mission_flow_v2/` PM Agent step | Full intake scan — tier, sensitive patterns, initial risk assessment |
| Pre-LLM delegation | `llm_delegation/router.py` | `local_only` enforcement for Tier 3 missions |
| `SECURITY_HARDEN` mission type | Specialist agent | Re-runs sensitive pattern scan on source code being hardened |

---

## Public API

### `assess_mission_risk(mission: MissionRecord) -> RiskAssessment`

The primary entry point. Runs all checks and returns a `RiskAssessment` dataclass.

```python
@dataclass
class RiskAssessment:
    tier: DataClassification
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "BLOCKED"]
    findings: list[SecurityFinding]
    local_only_required: bool
    permitted_output_modes: list[OutputMode]
    permitted_depth_modes: list[DepthMode]
    assessed_at: str  # UTC ISO-8601
```

If `risk_level == "BLOCKED"`, the caller must not proceed with the mission. `mission_flow_v2/` transitions the mission to `FAILED` with a `MISSION_SECURITY_COMPLIANCE_WARNED` event and the `RiskAssessment` serialized into `metadata["risk_assessment"]`.

### `SecurityFinding`

```python
@dataclass
class SecurityFinding:
    rule_id: str          # e.g., "SEC-CRED-001", "SEC-PII-003"
    severity: Literal["INFO", "WARN", "ERROR", "CRITICAL"]
    location: str         # "prompt", "attachment:{file_id}", "metadata"
    description: str
    remediation: str
```

`CRITICAL` findings always produce `risk_level == "BLOCKED"`. `ERROR` findings produce `HIGH`. Multiple `WARN` findings may escalate to `HIGH`.

### `enforce_local_only(agent_key: str, persona: AgentPersona) -> None`

Called by `llm_delegation/router.py` before routing any LLM call for a Tier 3 mission. Raises `LocalOnlyViolation` if `persona.local_only` is `False` and the mission's classification is `TIER_3_REGULATED`.

```python
class LocalOnlyViolation(Exception):
    """Raised when a cloud-provider LLM call is attempted for a Tier 3 mission."""
```

### `check_output_mode_permitted(mission: MissionRecord) -> bool`

Returns `True` if the mission's `OutputMode` is in the permitted set for its `DataClassification` tier. Called at intake before PM Agent begins chartering.

---

## Detection Rules

Sensitive pattern detection is implemented as a priority-ordered rule list. Each rule has an ID, a compiled regex, a severity, and a remediation hint. Rules are evaluated against the mission prompt text and any extracted attachment content (`MissionAttachment.content`).

### Rule Categories

| Category | Prefix | Examples |
|---|---|---|
| Credential patterns | `SEC-CRED-*` | API keys, private key headers, password assignments in code |
| PII markers | `SEC-PII-*` | SSN patterns, IBAN formats, passport number regexes |
| Regulated domain keywords | `SEC-REG-*` | HIPAA-adjacent terms (PHI, ePHI), PCI-DSS terms (cardholder, PAN) |
| Secrets in code | `SEC-SECRET-*` | Base64-encoded tokens, JWT headers, bearer token patterns |
| Export-controlled terms | `SEC-EXPORT-*` | ITAR/EAR keyword list |

### Tier-to-Permitted-Mode Matrix

| DataClassification | Permitted OutputModes | Permitted DepthModes | `local_only` required |
|---|---|---|---|
| `TIER_0_PUBLIC` | All | All | No |
| `TIER_1_INTERNAL` | All | All | No |
| `TIER_2_SENSITIVE` | All except `APPLY_PATCH` direct on production | All | No |
| `TIER_3_REGULATED` | `ANALYZE_ONLY`, `PLAN_ONLY`, `PATCH_PROPOSAL` | `SPRINT`, `STANDARD` | **Yes** |

---

## Integration with Audit Evidence

The `RiskAssessment` returned by `assess_mission_risk()` is:

1. Written to `mission.metadata["risk_assessment"]` by the PM Agent step
2. Included verbatim in the audit report bundle by the audit worker (`storage_artifacts.upsert_audit_report()`)
3. Referenced in the compliance evidence mapping (`COMPLIANCE_EVIDENCE_MAPPING.md`)

All `SecurityFinding` records with severity `WARN` or above are also emitted as `MISSION_SECURITY_COMPLIANCE_WARNED` events on the `sigma` Protocol Bus stream.

---

## Related Docs

- `DATA_CLASSIFICATION_POLICY.md` — defines the tier system this module enforces
- `SENSITIVE_CODE_HANDLING_POLICY.md` — defines the sensitive code handling rules
- `LLM_DELEGATION.md` — documents where `enforce_local_only()` is called
- `COMPLIANCE_EVIDENCE_MAPPING.md` — maps this module's outputs to compliance controls
