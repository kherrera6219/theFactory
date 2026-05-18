# Mission Flow v2 Comparison Audit (2026-03-08)

Document version: 2026.03.08
Last updated: 2026-03-08
Status: Historical Archive

> Historical note (2026-03-29): This document predates the current 38-agent runtime. Treat any `35-agent` references below as historical planning terminology unless explicitly updated in a newer canonical document.

## Scope
Compared:
- `HGR_Mission_Flow_v2.docx` (root)
- `HGR_Mission_Flow_v1_1.docx` + canonical source `docs/MISSION_FLOW_V1_1_CANONICAL_2026-03-07.md`
- Live runtime behavior (Gateway/Orchestrator APIs) on 2026-03-08.

## Update (Post-Implementation)
- Completion integrity guardrails are now implemented in both legacy and LangGraph lifecycle paths.
- Missions emit `MISSION_COMPLETION_BLOCKED` and halt before `COMPLETE` when both pod-assignment and logicnode artifacts are absent (unless policy-exempt).
- Chain-of-command trace is now available in runtime APIs and Mission Control mission detail.

## High-Confidence Findings
1. `v2` is more detailed but mixes implemented behavior with aspirational behavior.
2. `v1.1` is aligned to canonical registry IDs and current lifecycle implementation.
3. Live runtime currently executes coarse lifecycle states with deterministic checkpoints, not the full `v2` 11-phase/state-machine model.

## Key Mismatches (`v2` vs Running App)
- `v2` claims an 11-phase pipeline and custom agent microstates (`VIBE_CAPTURE`, `GRAND_FUSION`, `OPTIMIZATION_DISPATCH`).
  - Runtime mission events are currently `MISSION_QUEUED`, `MISSION_RUNNING`, `MISSION_GATING`, `MISSION_FUSION`, `MISSION_VERIFIED`, `MISSION_COMPLETE`.
- `v2` claims strict deep QC loops with 1,000 simulation tests and 0.0001% tolerance as active gating.
  - Current runtime does not enforce these as hard lifecycle blockers by default.
- `v2` introduces non-canonical roles in active flow text (`Data Architect`, `SRE Agent`).
  - Canonical 35-agent registry uses support ring IDs/names in `agent_registry.py` and does not expose those as standalone canonical agent IDs.
- `v2` implies guaranteed artifact production before completion.
  - Runtime now enforces artifact-gated completion; this mismatch is closed.

## Live Runtime Evidence (2026-03-08)
- Gateway health: auth mode `api_key`, orchestrator healthy.
- Orchestrator health: `langgraph_enabled=false`, auto transitions enabled, mission lifecycle active.
- Mission events for `mission-df5f08ba-e6be-4bcf-a900-b59e3e9313e3`: only queued/running/gating/fusion/verified/complete.
- Operations summary shows empty `pod_assignment_counts`.
- Internal operations endpoints currently return empty logicnode and pod-assignment sets for recent runs.

## Required Application Updates
1. Enforce mission-completion integrity gates (no `COMPLETE` with missing required artifacts unless policy-exempt).
2. Resolve pod-worker internal auth key mismatch so internal writes (pod assignment/logicnode/audit artifacts) persist reliably.
3. Enforce strict PM -> CEO -> pod-manager routing under dedicated profile and expose per-mission chain trace in API/UI.
4. Add integration tests that assert non-zero assignments + logicnodes for representative missions.
5. Product decision: either:
   - Implement `v2` 11-phase/state-machine model in runtime and UI, or
   - Keep 7-phase mapped model and label `v2` details as roadmap/aspirational.


