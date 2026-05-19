# Phase 27 — Mission Control Convergence and Final Release Qualification

**Status:** Planned
**Last updated:** 2026-05-18
**Depends on:** Phase 26 (production hardening complete, all gates green)
**Frontend supplement:** See `Frontend_Phase_Updates.md` for full type
definitions, component specs, and cumulative frontend checklist.

---

## Problem

After Phases 15–26, the backend has capabilities that Mission Control does
not yet fully surface. Every phase from 19–25 added new chain trace events,
new metadata fields, and new evidence panels — some were defined as "render
in Mission Control" in those phases, but a final pass is needed to verify
all surfaces are consistent, all panels render real data, and no placeholder
copy or stale UI state remains.

This is the convergence and final qualification phase. Its output is a
production-ready system with full operator visibility, green E2E coverage,
and a release candidate that passes the final release gate.

---

## Pre-work carried forward from earlier phases

These frontend items must be complete before Phase 27 convergence begins.
Track in `Frontend_Phase_Updates.md`.

| Item | Phase | Status |
|---|---|---|
| Clear stale `.tsbuildinfo`, fix `null` safety in `repo/review/route.ts` | 15 (pre-work) | — |
| Add AGENT-39/40/41 to `STATIC_AGENT_SLOTS` | 15 | — |
| Extract Mission Detail panels into `panels/` directory | 19 | — |
| Add `ErrorBoundary` component | 19 | — |
| Replace `window.confirm` dialogs | 19 | — |
| PM clarification panel + API client functions | 19 | — |
| `LlmUsageSummary`, `VcCommitStrategy`, `IntegrationTests`, etc. | 15–20 | — |
| `PodAuditVerdict`, `TestdataManifest`, `RuntimeQcReport` | 21–22 | — |
| `SbomDelta`, PORT phase indicator types | 23–24 | — |
| All new evidence panels rendering with data and empty states | 19–25 | — |

---

## Change 1 — Mission Control evidence panel audit

Verify every panel added in Phases 15–26 against the live backend. For each:
- Confirm the chain trace field it reads exists in a real COMPLETE mission.
- Confirm the panel renders when data is absent (empty state — not crash).
- Confirm the panel renders when data is present.
- Remove any hardcoded fallback values masking missing backend data.

Panels to audit:

| Panel | Added in | Chain trace field |
|---|---|---|
| Mission Cost | Phase 15 | `llm_usage_summary` |
| PM Clarification | Phase 19 | `pm_clarification` |
| CEO Reasoning Summary | Phase 20 | `CEO_REASONING_SUMMARY` event |
| Security Threat Analysis | Phase 20 | `security_compliance_report.threat_analysis` |
| VC Commit Strategy | Phase 20 | `vc_commit_strategy` |
| Generated Tests | Phase 20 | `integration_tests` |
| Provider Health (Broker) | Phase 21 | `/internal/broker/provider-health` |
| Pod Audit Verdict | Phase 21 | `pod_audit_verdict` |
| Deploy Readiness | Phase 21 | `deploy_readiness` |
| Runtime QC | Phase 22 | `runtime_qc_report` |
| Test Environment | Phase 22 | `testdata_manifest` |
| SBOM Delta | Phase 23 | `sbom_delta` |
| PORT Phase Indicator | Phase 24 | `port_phase`, `port_source_language` |
| Prompt Registry | Phase 25 | `/internal/prompt-registry` |

For any panel that is missing or broken, implement the fix in this phase.

---

## Change 2 — E2E coverage for new mission outcomes

Add Playwright tests for the key journeys that exist after Phase 22:

```
apps/mission-control/e2e/
  mission-build-new-complete.spec.ts
  mission-analyze-only.spec.ts
  mission-runtime-qc.spec.ts
  mission-cost-panel.spec.ts
  mission-deploy-readiness.spec.ts
  mission-reduce-deps.spec.ts
```

Each spec uses mock mission state fixtures for CI (no live stack required).
A `@pytest.mark.demo` tagged suite covers the live-stack path via `make demo`.

---

## Change 3 — Documentation reconciliation

**`docs/IMPLEMENTATION_STATUS.md`**
- Update "Current active phase" to Phase 27.
- Add summary rows for Phases 15–26.
- Update "Release blockers" to "None — all blockers resolved."

**`docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md`**
- Verify all "Is" claims hold against current implementation.
- Remove any "Is Not" claims that are now implemented (runtime QC is
  real after Phase 22, DEPABS executes after Phase 23, etc).

**`docs/ROADMAP.md`**
- Append Phase 40–52 entries mapping to Phases 15–27.

**`README.md`**
- Update Quick Start to reflect current `make up` → `make demo` flow.

**`AGENTS.md`**
- Update "Last validated" date to Phase 27 completion date.
- Add AGENT-40, AGENT-41 activation status.
- Remove stale gap entries — all previously-listed gaps resolved.
- Add Phase 19–22 settings to the settings reference table.

**`docs/AGENT_LLM_PROVIDER_MODEL_MATRIX_2026-03-02.md`**
- Add AGENT-40-TESTDATA and AGENT-41-RQCA rows.
- Note Phase 22 activation status for both.

---

## Change 4 — Accessibility and performance gates

Run Lighthouse CI on Mission Detail page after all panels land:

```bash
cd apps/mission-control
npm run build
npm run test:perf
```

Thresholds: performance ≥ 85, accessibility ≥ 90.

Fixes required before passing:
- All new panels must have `role`, `aria-label`, keyboard-navigable controls
- `ErrorBoundary` wrapping prevents crash on bad data
- No `window.confirm` calls remaining

---

## Change 5 — Final release gate execution

Run the complete release gate in a clean environment:

```bash
make validate        # lint + schema + pytest + npm lint/test
make promotion-gate  # intelligence-layer gate checks
make eval            # Phase 25 offline AI evals
make demo            # Phase 18 demo missions against live stack
python scripts/production_review_audit.py  # SEC-KEY-001, DR-001, etc.
```

Record evidence in:
```
docs/evidence/phase27_final_release_qualification_2026-MM-DD.md
```

---

## Exit criteria — Phase 27 complete = system is production-ready

### Backend
- [ ] `python -m pytest -q` green in clean environment
- [ ] `python -m ruff check services tests scripts` green
- [ ] Coverage gate ≥ 80% (`--cov-fail-under=80`)
- [ ] `make promotion-gate` all gates green or documented skip
- [ ] `make eval` all offline safety and PM contract evals green
- [ ] `make demo` all 3 demo missions COMPLETE with non-empty generated code

### Frontend
- [ ] `npm run lint` — 0 errors (stale cache cleared, null safety fixed)
- [ ] `npm test` — all unit tests green
- [ ] All 14 evidence panels in the audit table verified against live data
- [ ] All new panels have empty-state handling (no crash on absent data)
- [ ] `ErrorBoundary` wraps every panel in Mission Detail
- [ ] No `window.confirm` calls remain
- [ ] AGENT-39/40/41 in `STATIC_AGENT_SLOTS`
- [ ] Mission Detail `page.tsx` ≤ 600 lines (panels extracted)
- [ ] New E2E specs green against mock fixtures
- [ ] Lighthouse performance ≥ 85, accessibility ≥ 90 on Mission Detail

### Documentation
- [ ] `docs/IMPLEMENTATION_STATUS.md` Phase 27 complete, no open blockers
- [ ] `AGENTS.md` last-validated date updated, all gap entries resolved
- [ ] `docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md` accurate against current system
- [ ] `README.md` quick start demo accurate and functional
- [ ] `docs/ROADMAP.md` Phase 40–52 entries appended

### Security and evidence
- [ ] `git log --all -- deploy/postgres/certs/server.key` — no output
- [ ] `git log --all -- deploy/redis/certs/redis.key` — no output
- [ ] DR drill evidence current (within 30 days)
- [ ] `docs/evidence/phase27_final_release_qualification_*.md` exists with
      all fields "pass"

**When all 25 exit criteria are checked: theFactory is production-ready.**
