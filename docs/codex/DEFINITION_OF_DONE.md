# Definition of Done — theFactory / Holy Grail Refinery

Document version: 2026.08.17  
Last updated: 2026-08-17  
Status: Canonical  
Audience: Developers, reviewers, and maintainers

A change is done only when every applicable item below is satisfied for the modified scope.

---

## 1. Tests

- [ ] `make test` passes with no failures and no coverage regressions (line ≥80%, branch ≥70%, mixed ≥80%)
- [ ] `make test-ui` passes (TypeScript lint + Vitest)
- [ ] `make test-ui-e2e` passes (Playwright), or the waiver is recorded below
- [ ] `make validate` passes when the change touches docs, schemas, APIs, runtime, or release-sensitive paths
- [ ] New behavior is covered by tests
- [ ] No new `pytest.mark.skip` or `pytest.mark.xfail` is added without a linked issue
- [ ] Test names describe what they verify, not how they verify it

## 2. Documentation

- [ ] Relevant `docs/` files reflect the changed behavior
- [ ] `AGENTS.md` is updated if runtime model, topology, lifecycle, or architecture changed
- [ ] Inline docstrings/comments match the current code path
- [ ] No new contradiction is introduced between docs and code
- [ ] OpenAPI snapshots are regenerated or `python scripts/export_openapi.py --check` passes when routes or schemas change

## 3. Extractor Changes

- [ ] Any extractor change includes a fixture comparison or equivalent before/after evidence
- [ ] Golden tests for extractors pass
- [ ] Extractor fallback behavior is preserved and explicit
- [ ] Downstream schema compatibility for LogicNodes / Refined-IR remains intact

## 4. API Contract

- [ ] External API contracts are unchanged unless explicitly approved
- [ ] New response fields are additive and optional unless guaranteed by all supported backends
- [ ] TypeScript types in `apps/mission-control/app/lib/types.ts` match the backend payloads

## 5. Runtime Topology

- [ ] Runtime/topology assertions remain accurate for the shipped default topology
- [ ] No UI or docs imply all 41 agents are isolated processes unless the dedicated profile is active
- [ ] Heartbeat/runtime metadata remains accurate and tested when changed

## 6. Security

- [ ] No secrets or credentials are added to code, docs, or config
- [ ] Auth-gated routes still enforce the intended dependency or role boundary
- [ ] Replay detection, deduplication, and circuit-breaker controls are not regressed

## 7. Scope

- [ ] The change does not widen scope beyond the assigned task without approval
- [ ] Out-of-scope gaps found during work are documented separately, not silently bundled in
- [ ] User-visible or operationally significant changes are documented where operators will see them

---

*Source: `AGENTS.md §6`. Update both files together if the standard changes.*
