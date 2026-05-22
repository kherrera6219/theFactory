# Phase 27 — Mission Control Convergence and Final Release Qualification

**Status:** ✅ COMPLETE
**Completed:** 2026-05-20
**Last updated:** 2026-05-22
**Depends on:** Phase 26 (production hardening complete, all gates green)
**Frontend supplement:** See `Frontend_Phase_Updates.md` for full type
definitions, component specs, and cumulative frontend checklist.

> **Completion summary:** See root-level `Phase_27_Mission_Control_Convergence.md` for
> completion evidence checklist. Mission Detail 22 panels, ErrorBoundary, 23 Playwright specs,
> 97 eval tests, all MissionChainTrace types — complete as of 2026-05-20.
> Phase 6-7 UI/UX improvements (command palette, guided tour, tooltip glossary, status bar,
> Electron shell) shipped 2026-05-22 on top of Phase 27 baseline.

---

## Pre-implementation findings (2026-05-20)

After reading the live codebase, the pre-work table from the May 18 plan
has been updated to reflect actual status:

| Item | Phase | Status |
|---|---|---|
| Clear stale `.tsbuildinfo`, fix `null` safety in `repo/review/route.ts` | 15 pre-work | ✅ Done |
| Add AGENT-36 through AGENT-41 to `STATIC_AGENT_SLOTS` | 15 | ✅ Done (gaps session) |
| `LlmUsageSummary` type + `getMissionTokenUsage` in api-client | 15 | ✅ Done (gaps session) |
| Gemini embedding path in `knowledge_embeddings.py` | 16 | ✅ Done (gaps session) |
| AIM language suffix map expanded (C/C++/Rust/Swift/Lua/GLSL etc.) | Gap 5 | ✅ Done (gaps session) |
| LLM-driven DEPABS replacement via AGENT-39 | Gap 6 | ✅ Done (gaps session) |
| PORT phase indicator types in `MissionChainTrace` | 24 | ✅ Done |
| PORT phase indicator rendered in Mission Signals panel | 24 | ✅ Done |
| Prompt registry endpoint + safety envelope | 25 | ✅ Done |
| 23 eval tests passing offline | 25 | ✅ Done |
| Extract Mission Detail panels into `panels/` directory | 19 | ⬜ Not done |
| `ErrorBoundary` component wrapping panels | 19 | ⬜ Not done |
| Replace `window.confirm` dialogs | 19 | ⬜ Not done |
| PM clarification panel + API route | 19 | ⬜ Not done |
| `VcCommitStrategy`, `IntegrationTests` types | 20 | ⬜ Not done |
| `PodAuditVerdict`, `TestdataManifest`, `RuntimeQcReport` types | 21–22 | Partial — RuntimeQcReport in types.ts |
| Mission Detail `page.tsx` ≤ 600 lines (panels extracted) | 27 | ⬜ Currently 1574 lines |
| New E2E specs green against mock fixtures | 27 | ⬜ Not done |
| Lighthouse performance ≥ 85, accessibility ≥ 90 | 27 | ⬜ Not measured |

---

## Problem

After Phases 15–25, the backend has capabilities that Mission Control does
not yet fully surface. The critical frontend gap is Mission Detail `page.tsx`
at **1574 lines** — far beyond the 600-line target. Every phase added new
panels inline rather than as extracted components. This phase extracts them,
adds missing types, and runs a final convergence pass.

---

## Change 1 — Mission Detail panel extraction

**File:** `apps/mission-control/app/(shell)/missions/[id]/page.tsx`
**Current:** 1574 lines — all panels inline
**Target:** ≤ 600 lines — panels extracted to `panels/` directory

Create:
```
apps/mission-control/app/(shell)/missions/[id]/panels/
  MissionSignalsPanel.tsx
  LogicNodeProgressPanel.tsx
  GeneratedOutputPanel.tsx
  EquivalenceReportPanel.tsx
  SecurityCompliancePanel.tsx
  DependencyAbsorptionPanel.tsx
  RuntimeQcPanel.tsx
  AimPanel.tsx
  FusionPanel.tsx
  DeliveryPanel.tsx
  AuditEvidencePanel.tsx
  CostPanel.tsx
  PortPhasePanel.tsx
```

Each panel receives only the props it needs from `chainTrace` and `mission`.
`page.tsx` becomes an orchestrator that assembles panels — no inline JSX logic.

---

## Change 2 — Missing types and empty-state handling

Add to `apps/mission-control/app/lib/types.ts`:

```typescript
export type VcCommitStrategy = {
  strategy: string;
  commit_message: string;
  branch_name?: string;
  source: string;
};

export type IntegrationTests = {
  test_code: string;
  framework: string;
  language: string;
  test_count: number;
  source: string;
};

export type PodAuditVerdict = {
  verdict: string;
  score: number;
  findings: string[];
  source: string;
};
```

Add these to `MissionChainTrace`:
```typescript
vc_commit_strategy?: VcCommitStrategy | null;
integration_tests?: IntegrationTests | null;
pod_audit_verdict?: PodAuditVerdict | null;
pm_clarification?: Record<string, unknown> | null;
llm_usage_summary?: LlmUsageSummary | null;
```

Every panel must handle `null` / `undefined` gracefully — no crash on absent data.

---

## Change 3 — ErrorBoundary component

Create `apps/mission-control/app/components/error-boundary.tsx`:

```typescript
"use client";
import { Component, type ReactNode } from "react";

type Props = { children: ReactNode; fallback?: ReactNode };
type State = { hasError: boolean; error?: Error };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback ?? (
        <p className="muted">Panel unavailable — data may be loading.</p>
      );
    }
    return this.props.children;
  }
}
```

Wrap every panel in Mission Detail with `<ErrorBoundary>`.

---

## Change 4 — Replace window.confirm

Search `apps/mission-control/` for `window.confirm` calls and replace
with a state-driven confirmation dialog using the existing `Panel` and
`SystemMessage` components. No `window.confirm` should remain in production
code.

---

## Change 5 — E2E specs for new mission outcomes

Add to `apps/mission-control/e2e/`:
```
mission-build-new-complete.spec.ts   — mock BUILD_NEW COMPLETE state
mission-cost-panel.spec.ts           — LlmUsageSummary panel renders
mission-runtime-qc.spec.ts           — RuntimeQcReport panel renders
mission-reduce-deps.spec.ts          — DependencyAbsorption panel renders
```

Each spec uses MSW (Mock Service Worker) or Next.js route mocking for CI.
No live stack required.

---

## Change 6 — Documentation reconciliation

### `docs/IMPLEMENTATION_STATUS.md`
- Update "Current active phase" to Phase 27 complete.
- Add summary rows for Phases 15–27.
- Change "Release blockers" to "None — all blockers resolved."

### `docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md`
- Verify all "Is" claims hold. In particular:
  - "A runtime QC platform" — now true after Phase 22.
  - "A dependency-reduction engine" — now true after Phase 23.
  - "A workspace-isolated execution environment" — verify RQCA sandbox.

### `AGENTS.md`
- Update "Last validated" date to Phase 27 completion date.
- Add AGENT-40-TESTDATA and AGENT-41-RQCA activation status.
- Remove all previously-listed gap entries — resolved in Phases 15–26.
- Add Phase 22–25 settings flags to the settings reference table.

### `README.md`
- Update Quick Start to `make up` → `make demo` → Mission Control.
- Update model strings to current values (gpt-5.5, claude-opus-4-7 etc.).

### `docs/ROADMAP.md`
- Append entries Phase 40–52 mapping to Phases 15–27.

---

## Change 7 — Final release gate execution

```bash
make validate        # lint + schema + pytest + npm lint/test
make eval            # Phase 25 offline AI evals (23 tests)
python scripts/production_review_audit.py  # Must be 22/22
make demo            # Phase 18 demo missions (requires live stack + keys)
```

Record evidence:
```
docs/evidence/phase27_final_release_qualification_2026-MM-DD.md
```

---

## Exit criteria — Phase 27 complete = production-ready

### Backend
- [ ] `python -m pytest -q` green
- [ ] `python -m ruff check services tests scripts` green
- [ ] Coverage ≥ 80%
- [ ] `make eval` all 23 offline eval tests green
- [ ] `make demo` all 3 demo missions COMPLETE (requires live stack)

### Frontend
- [ ] `npm run lint` — 0 errors
- [ ] `npm test` — all unit tests green
- [ ] Mission Detail `page.tsx` ≤ 600 lines (panels extracted)
- [ ] `ErrorBoundary` wraps every panel
- [ ] No `window.confirm` calls remain
- [ ] All 14 evidence panels verified: render with data, render empty state
- [ ] New E2E specs green against mock fixtures
- [ ] Lighthouse performance ≥ 85, accessibility ≥ 90

### Documentation
- [ ] `docs/IMPLEMENTATION_STATUS.md` — Phase 27 complete, no open blockers
- [ ] `AGENTS.md` last-validated date updated, AGENT-40/41 activation noted
- [ ] `docs/WHAT_THEFACTORY_IS_AND_IS_NOT.md` accurate against current system
- [ ] `README.md` quick start accurate
- [ ] `docs/ROADMAP.md` Phase 40–52 appended

### Security and evidence
- [ ] `git log --all -- deploy/postgres/certs/server.key` — no output
- [ ] `git log --all -- deploy/redis/certs/redis.key` — no output
- [ ] DR drill evidence current (within 30 days)
- [ ] `production_review_audit.py` — 22/22 checks pass
- [ ] `docs/evidence/phase27_final_release_qualification_*.md` present

**When all criteria are met: theFactory is production-ready.**
