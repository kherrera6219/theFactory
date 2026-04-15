# Code Review Checklist — theFactory / Holy Grail Refinery

Use this checklist when reviewing or self-reviewing a PR.

---

## Author checklist (complete before requesting review)

- [ ] All Definition of Done items satisfied
- [ ] `make validate` passes locally (ruff + schema validation + pytest + npm lint/test)
- [ ] PR description explains *why*, not just *what*
- [ ] Breaking changes clearly flagged
- [ ] Sensitive files excluded (`.env`, `*.key`, `deploy/.local/`)

## Reviewer checklist

### Correctness
- [ ] Logic matches stated intent
- [ ] Edge cases handled (empty lists, null fields, network errors)
- [ ] No silent swallowing of exceptions without logging

### Security
- [ ] No new secrets in code or comments
- [ ] Auth boundaries respected — internal routes use `INTERNAL_AUTH_DEP`
- [ ] User input validated at system boundaries

### Architecture fitness
- [ ] Follows existing module boundaries (no new cross-cutting imports)
- [ ] New modules added to `__init__.py` where appropriate
- [ ] No duplicated logic that should be centralised

### TypeScript / Frontend
- [ ] New API response fields reflected in `types.ts`
- [ ] No hardcoded counts or topology-specific copy
- [ ] Accessibility: `aria-*` attributes on interactive/status elements

### Tests
- [ ] Test coverage added for new code paths
- [ ] Mocks at correct module level (avoid patching re-exported names)
- [ ] No tests that only test the mock

---

## Waiver log

If a checklist item is waived, record it here with justification.

| PR | Item waived | Reason | Author |
|----|-------------|--------|--------|
|    |             |        |        |
