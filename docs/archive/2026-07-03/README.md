# 2026-07-03 Archive

Document version: 2026.07.03
Last updated: 2026-07-03
Status: Historical
Audience: Maintainers and auditors

This archive bucket contains documents moved out of the active docs map
during the 2026-07-03 documentation inventory/reduction pass, which
audited every active document against the current codebase and pruned the
set down to what a production application should ship.

## Archived Documents

| File | Reason archived | Current source of truth |
|---|---|---|
| `AUDIT_PLAN.md` | Completed, dated audit initiative (2026-06-21); findings tracker is closed except one item already tracked elsewhere | `docs/CURRENT_TODO.md`, `docs/IMPLEMENTATION_STATUS.md` |
| `FIRST_FULL_SYSTEM_RUN_FINDINGS_2026-06-30.md` | Point-in-time findings report from a specific test session; recommendations already folded into current TODO/handoff | `docs/CURRENT_TODO.md`, `docs/HANDOFF_CURRENT.md` |
| `MISSION_TESTS_SESSION_LOG_2026-06-30.md` | Companion chronological session log to the findings report above; fully retrospective | `docs/HANDOFF_CURRENT.md` |
| `PROTOCOL_BUS_LANE_ACTIVATION_PLAN.md` | PBLA Stage 1 is code-complete and live-validated; this was the implementation plan for that now-finished stage | `docs/PROTOCOL_BUS_PROGRAM_ROADMAP.md` |
| `PROTOCOL_BUS_MISSION_BATTERY_PLAN.md` | Test plan for the 20-mission battery that has already been executed (see the findings/session-log docs archived alongside it) | `docs/CURRENT_TODO.md` |
| `UPDATE_PLAN_VERIFICATION_HARDENING_2026-06-29.md` | Dated hardening plan; all phases marked done in the doc's own progress tracker | `docs/CURRENT_TODO.md` |
| `STACK_REMEDIATION_PLAN_2026-07-01.md` | Dated live-ops incident postmortem/remediation plan; findings resolved and fixed per subsequent commits | `docs/CURRENT_TODO.md` |
| `AGENT_PROTOCOL_BUS_DATA_SYSTEMS_PLAN.md` | Status was self-declared "Reference"; every phase marked complete; content overlaps `PROTOCOL_BUS_PROGRAM_ROADMAP.md` and the live `/v1/operations/agent-integrations` endpoint | `docs/PROTOCOL_BUS_PROGRAM_ROADMAP.md`, `README.md` |
| `HANDOFF_CURRENT_OLDER_HISTORY.md` | Split out of `docs/HANDOFF_CURRENT.md`'s "Latest Completed Work" section, which had grown to 1500+ lines with entries going back months; kept only the 2026-07-02/07-03 review-sweep entries live | `docs/HANDOFF_CURRENT.md` |
| `CURRENT_TODO_OLDER_HISTORY.md` | Split out of `docs/CURRENT_TODO.md`'s "Recently Completed" section, same accumulation pattern as above | `docs/CURRENT_TODO.md` |

## Deleted (not archived — described systems/classes that never existed in the code)

The 2026-07-03 pass also found three active docs describing an aspirational
system rather than the actual implementation, with no salvageable content:

- `docs/EQUIVALENCE_VERIFIER.md` — described a fictional `EquivalenceReport`
  dataclass/3-plane AIM-comparison system; the real `equivalence_verifier.py`
  is a deterministic per-check contract validator (`build_equivalence_report`).
- `docs/IS_AGENT.md` — described a fictional "Integration Specialist" agent
  class with circuit breakers and outbound calls; the real `is_agent.py`
  seeds static Knowledge Lake bootstrap documents.
- `docs/PORT_COORDINATOR_AND_LOGICNODE_SCHEMA.md` — described a fictional
  Redis-backed ephemeral port allocator; the real `port_coordinator.py`
  orchestrates PORT-mission two-phase source/target extraction. Its
  LogicNode-schema half duplicated content already correctly superseded by
  `docs/LOGICNODE_SCHEMA.md`.
- `docs/diagrams/ENTERPRISE_ARCHITECTURE_DIAGRAMS.md` — near-total overlap
  with `docs/ARCHITECTURE_DIAGRAMS.md`, plus unverified/aspirational claims
  (Windows DPAPI keystore, mutual TLS between internal services) not
  corroborated anywhere else in the codebase or its canonical sibling doc.
