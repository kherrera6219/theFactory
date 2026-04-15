# PR Review Checklist — theFactory / Holy Grail Refinery

Document version: 2026.04.14  
Last updated: 2026-04-14  
Status: Canonical  
Audience: Authors, reviewers, and maintainers

Use this checklist for every pull request. The author fills it out; the reviewer verifies it.

---

## Author checklist

### Tests & CI
- [ ] `make lint` passes
- [ ] `make test` passes
- [ ] `make test-ui` passes
- [ ] `make test-ui-e2e` passes, or the waiver is recorded below
- [ ] `make validate` passes when the change touches schema/runtime-sensitive areas

### Code correctness
- [ ] Every touched file was read before it was changed
- [ ] The diff matches the task and does not introduce unrelated scope
- [ ] Edge cases and failure paths are handled explicitly

### Extractors
- [ ] Fixture comparison included for extractor changes
- [ ] Golden extractor tests pass
- [ ] Extraction method / fallback behavior stays accurate

### Orchestrator / Runtime
- [ ] Lifecycle event and state transition behavior remains consistent
- [ ] Topology/runtime metadata remains accurate
- [ ] Internal write paths still respect auth and persistence boundaries

### Mission Control / Frontend
- [ ] UI types match backend payloads
- [ ] No fictional topology, agent count, or mocked production state is introduced
- [ ] Accessibility/status affordances remain intact where UI changed

### Security
- [ ] No new secrets in code or config
- [ ] Auth checks are not bypassed or weakened
- [ ] Replay/dedup/circuit-breaker controls remain intact where applicable

### Documentation
- [ ] Relevant docs reflect the behavior change
- [ ] `AGENTS.md` updated if architecture/topology/lifecycle changed
- [ ] No new doc-to-code contradiction introduced

---

## Reviewer checklist

- [ ] Diff is consistent with the stated intent
- [ ] Tests cover the changed code paths
- [ ] The Definition of Done in `docs/codex/DEFINITION_OF_DONE.md` is satisfied
- [ ] No conflict markers, dead code, or accidental debug scaffolding remain

---

## Waiver log

If any item above is waived, record it here with a reason.

| Item waived | Reason | Approved by |
|---|---|---|
| | | |

---

*Derived from `AGENTS.md §6` and `docs/codex/DEFINITION_OF_DONE.md`.*
