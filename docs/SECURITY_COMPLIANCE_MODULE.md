# Security Compliance Module

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Developers and operators

**Source file:** `services/orchestrator/orchestrator/security_compliance.py`
**Role:** Deterministic, static (no code execution) gate that scans a mission's *generated output* for hardcoded secrets, dangerous API usage, and AIM-flagged risk before the mission is allowed to complete. Called once per mission from the delivery phase (`mission_flow_v2/phases_delivery.py`'s `_prepare_security_compliance_report`), not at intake.

This document was rewritten on 2026-07-03 — the previous version described an `assess_mission_risk()`/`RiskAssessment`/`SecurityFinding`/`enforce_local_only()` API that never existed in this file.

---

## Overview

`mission_requires_security_compliance(metadata)` gates whether the check runs at all — it returns `True` only if the mission has `generated_output`, an `application_intelligence_map`, or non-empty `source_code`. If none of those are present, the delivery phase treats the gate as skipped (`{"skipped": True, ...}`) and the mission proceeds.

When required, `build_security_compliance_report(mission_id, metadata, enforcement_enabled)` runs six independent checks and combines them into one report:

| Check | Category | `required` | What it does |
|---|---|---|---|
| `secret_pattern_scan` | security | **True** | Regex scan of `generated_output.generated_code` for `key/secret/token/password = "..."`-style assignments and `sk-...`-shaped API key strings |
| `dangerous_api_scan` | security | False (warn-only) | Regex scan for `eval(`/`exec(`/`subprocess.(Popen\|run\|call)(`/`child_process`/`dangerouslySetInnerHTML`/`innerHTML =` |
| `aim_risk_flags` | security | False (warn-only) | Flags AIM `risk_flags` entries of `security`/`data`/`approval` |
| `equivalence_evidence_present` | compliance | **True*** | Requires `equivalence_report.passed == True` when `generated_output` exists (*not required if there's no generated output to check*) |
| `data_classification` (`_check_data_classification`) | compliance | varies | Cross-checks the mission's declared data classification against its content |
| `provenance` (`_check_provenance`) | compliance | varies | Cross-checks generated-output provenance metadata |

Both the regex-based scans are heuristic, not a hard security control — they are trivially evadable by generated code that builds a secret string via concatenation, `getattr`-based obfuscation, or an equivalent-but-unmatched API call shape (e.g. `os.system(...)`, which the `dangerous_api_scan` regex does not currently match). This is an accepted limitation of a static-regex scanner, not a bug to be patched reflexively.

## Blocking Logic

```python
should_block = bool(failed_required) and (enforcement_enabled or regulated_context)
```

- `failed_required` — any check with `required=True` that returned `status="fail"`.
- `enforcement_enabled` — the `mission_security_compliance_enforcement_enabled` setting (see `SETTINGS_REFERENCE.md`; **defaults to `true` as of 2026-07-03**, was `false`).
- `regulated_context` (`_requires_blocking_context`) — `True` if `metadata["depth_mode"]`, `mission_charter["depth_mode_label"]`, or the mission's data classification is `REGULATED`/`TIER_3_REGULATED`, **regardless of the enforcement flag** — a regulated mission always blocks on a failed required check.

`report["status"]` is `"blocked"` (should_block), `"warned"` (a required/optional check failed or warned but didn't block), or `"passed"`. `report["blocking"]` (the boolean) is what the delivery-phase caller actually reads to decide whether to halt the mission.

## Idempotency

`_prepare_security_compliance_report` caches the built report in `metadata["security_compliance_report"]` and returns it unchanged on any subsequent call for the same mission (the delivery-phase preparer re-runs its whole body on every completion-gate retry, e.g. after an orchestrator restart) — without this cache, the report would be rebuilt and re-signed every retry, and its audit event would fire again each time.

## Signing

The report is signed via `shared_runtime.crypto_signing.sign_payload` (ECDSA P-256/SHA-256) before being stored, producing a `signature_record` field. Signing failures are caught and logged — the report is still stored and still gates delivery, just without a `signature_record`. `get_build_artifact`'s equivalent artifact-verification re-check pattern (see `STORAGE_LAYER.md`) is the model for how a consumer should independently re-verify a report's integrity rather than trusting a stored `verified`/`passed` flag at face value.

---

## Related Docs

- `DATA_CLASSIFICATION_POLICY.md` — the tier system this module's `data_classification` check cross-references
- `SENSITIVE_CODE_HANDLING_POLICY.md` — policy intent behind the secret/dangerous-pattern scans
- `RUNTIME_QC_AND_TEST_ENVIRONMENTS.md` — the sibling RQCA runtime-QC gate, which has the same enforcement-flag-default pattern
- `COMPLIANCE_EVIDENCE_MAPPING.md` — maps this module's report to compliance controls
