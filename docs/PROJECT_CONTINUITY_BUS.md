# Project Continuity Bus

Document version: 2026.08.21
Status: Implemented (foundation)
Audience: Maintainers and AI coding agents

## Purpose

When a user keeps adding work to the same project, the factory must **resume** shared state — not start a blank mission every time.

This is the runtime equivalent of operator `HANDOFF` + `TODO` + plan authority:

| Artifact | Runtime table / field |
|----------|------------------------|
| Project identity | `projects.project_id` (extends existing `missions.project_id`) |
| Handoff | `project_handoff` — phase, next action, blockers, last mission, plan revision |
| Work ledger | `project_work_items` — open / in_progress / blocked / done |
| Plan authority | `projects.plan_authority_json` + handoff `authority_json` |

## Lifecycle

1. **PM intake** (`phases_intake._prepare_pm_intake`) calls `ensure_project_bus_for_mission` after the feature contract is produced.
   - First mission: create project + handoff; seed work items from acceptance criteria.
   - Follow-on: load handoff; claim unassigned open items; refresh plan authority.
2. **Delivery** (`phases_delivery._prepare_delivery_summary`) calls `finalize_project_bus_for_mission` with outcome `complete` and an evidence ref.
   - Marks work items claimed by this mission as `done` **only** with evidence.
   - Updates handoff next action to `await_follow_on`.
3. Blocked / failed outcomes update handoff blockers and may set project status `paused` without inventing completion.

## Code map

| Path | Role |
|------|------|
| `migrations/V010_project_continuity_bus.sql` | Schema |
| `storage_projects.py` | Persistence |
| `project_bus.py` | ensure / finalize orchestration |
| `storage.py` | Re-exports |
| `mission_flow_v2/phases_intake.py` | ensure hook |
| `mission_flow_v2/phases_delivery.py` | finalize hook |
| `tests/services/test_project_bus_unit.py` | Unit tests |

## Explicit non-goals (this change)

- Mission Control project detail UI (follow-up)
- Public API routes for work-item CRUD (follow-up; storage is ready)
- Auto-closing work items without mission claim + evidence
- Replacing per-mission SOW / QC gates

## Follow-ups

1. `GET /projects/{project_id}` and continue-mission intake that requires `project_id`
2. Mission Control project page: handoff + ledger + mission list
3. Brownfield / ZIP import attaches to the same `project_id` bus
4. Optional: on QC fail path, call `finalize_project_bus_for_mission(..., outcome="blocked")`
