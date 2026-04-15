# Definition of Done — theFactory / Holy Grail Refinery

A change is **done** when every item below is satisfied for the modified scope.

---

## 1. Tests

- [ ] All existing tests pass (`pytest --tb=short -q`)
- [ ] New behaviour is covered by unit tests
- [ ] No integration tests skipped that cover the changed path
- [ ] Test names describe *what* they verify, not *how*

## 2. Documentation

- [ ] `AGENTS.md` updated if runtime model, topology, or lifecycle changes
- [ ] Inline docstrings updated for changed public functions/classes
- [ ] `docs/reviews/` finding updated if a gap was closed

## 3. Extraction Engine

- [ ] `PythonAstExtractor` enabled under `PYTHON_AST_EXTRACTOR_ENABLED=true` flag
- [ ] AST extractor falls back to regex on `SyntaxError` — no silent failures
- [ ] `ExtractedConcept` schema matches LogicNode schema expected by orchestrator

## 4. API Contracts

- [ ] TypeScript types in `apps/mission-control/app/lib/types.ts` match orchestrator JSON
- [ ] New response fields are optional (`?`) unless the backend guarantees them in all versions
- [ ] No hardcoded agent counts in UI copy (e.g. "38-agent" → "multi-agent")

## 5. Topology Assertions

- [ ] `runtime_class` derived correctly for all 38 registry entries (verified via test)
- [ ] `topology_mode` exposed in `/internal/operations/summary` and `/internal/operations/agents`
- [ ] Mission Control runtime panel reflects live `topology_mode` from API

## 6. Security

- [ ] No new hardcoded secrets or credentials
- [ ] Auth-gated routes use `INTERNAL_AUTH_DEP` or equivalent
- [ ] `AUTH_MODE` and `MCP_API_KEY` validated at startup in non-development environments

## 7. Scope

- [ ] No speculative features added beyond the ticket
- [ ] Backwards-incompatible changes flagged in PR description
- [ ] `CHANGELOG` entry added for user-visible changes (if project maintains one)
