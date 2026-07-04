# Data Classification Policy

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Canonical
Audience: Operators, developers, maintainers, and security reviewers

This document was rewritten on 2026-07-03 — the previous version described a 4-level `PUBLIC`/`INTERNAL`/`CONFIDENTIAL`/`RESTRICTED` taxonomy with an elaborate retention/access-control matrix that had no relationship to the actual code. The real classification enum, its actual usage, and its actual (much thinner) enforcement are described below.

## The Real Classification Enum

`services/orchestrator/orchestrator/models.py`'s `DataClassification` enum defines exactly four values:

```python
class DataClassification(str, Enum):
    tier_0_public = "TIER_0_PUBLIC"
    tier_1_internal = "TIER_1_INTERNAL"
    tier_2_sensitive = "TIER_2_SENSITIVE"
    tier_3_regulated = "TIER_3_REGULATED"
```

## Where It's Set and Read

- A mission's `data_classification` is set on `mission.metadata["data_classification"]`, typically by the api-gateway when it detects sensitive content in the intake prompt (`_build_sensitive_input_scan` in `services/api-gateway/api_gateway/main.py`) — it sets `"TIER_2_RESTRICTED"` on detection and defaults to `"TIER_1_INTERNAL"` otherwise.
- **Known naming inconsistency, not yet reconciled:** the api-gateway writes the string `"TIER_2_RESTRICTED"`, not the orchestrator's actual enum value `"TIER_2_SENSITIVE"`. This doesn't crash anything (the orchestrator's `storage_missions.py` parses a *different* metadata key, `__data_classification__`, defensively inside a `try/except ValueError`), but it does mean `security_compliance.py`'s classification-based checks (below) never recognize an api-gateway-tagged "restricted" mission as anything other than an unrecognized/blank classification, since those checks only match on the literal strings `"TIER_3_REGULATED"` or `"REGULATED"`.
- `security_compliance.py`'s `_check_data_classification()` and `_requires_blocking_context()` read `metadata["data_classification"]` (or `mission_charter["data_classification"]`) and only special-case `TIER_3_REGULATED`/`REGULATED`:
  - `_check_data_classification()` marks the check `manual_review` (non-blocking on its own) when the classification is regulated, `pass` otherwise.
  - `_requires_blocking_context()` returns `True` for a regulated classification (or `depth_mode == "REGULATED"`), which forces the security-compliance report to block delivery on any failed required check **regardless of** the `mission_security_compliance_enforcement_enabled` setting (see `SECURITY_COMPLIANCE_MODULE.md`).
- `TIER_0_PUBLIC`, `TIER_1_INTERNAL`, and `TIER_2_SENSITIVE` have no distinct enforcement behavior today beyond that regulated-vs-not-regulated split — there is no separate access-control matrix, retention policy, or per-tier handling automation implemented in code for those three tiers.

## What This Means in Practice

The classification system as actually implemented is a single binary gate — "is this mission regulated, yes or no" — not a four-tier handling framework. If your organization needs the richer retention/access-control/incident-response policy that a prior version of this document described, that policy needs to be built (or enforced procedurally outside the codebase); it is not something the current code does for you.

## Related Docs

- `SECURITY_COMPLIANCE_MODULE.md` — the gate that actually reads this classification
- `SENSITIVE_CODE_HANDLING_POLICY.md` — the detection heuristics that set `TIER_2_RESTRICTED` on the api-gateway side
