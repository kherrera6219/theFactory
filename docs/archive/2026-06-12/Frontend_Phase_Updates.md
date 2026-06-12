# Frontend Updates — Phases 15–27

**Status:** Canonical supplement to phase plans
**Last updated:** 2026-05-18
**Purpose:** Tracks all frontend work required across the intelligence-layer
phases (15–27) that was identified in the Phase 27 frontend review.

---

## Immediate pre-work (before Phase 15 ships)

### Fix 1 — Clear stale TypeScript build cache

`npm run lint` is red due to a stale `.tsbuildinfo` file. The exported
functions (`listMissions`, `getMission`, `getMissionEvents`) exist in
`api-client.ts` and are imported correctly — the errors are cache artifacts.

```bash
cd apps/mission-control
rm -rf .next tsconfig.tsbuildinfo
npm run lint
npm test
```

Both must be green before any Phase 15 code is written.

### Fix 2 — Null safety in `app/api/repo/review/route.ts` line 543

```typescript
// Before (uses ! non-null assertion — fails TypeScript 6):
!testPlan.some((step) => step.toLowerCase().includes(params.requestedTargetLanguage!))

// After (use nullish coalescing):
!testPlan.some((step) =>
  step.toLowerCase().includes(params.requestedTargetLanguage ?? "")
)
```

### Fix 3 — Add AGENT-39/40/41 to `STATIC_AGENT_SLOTS` in settings page

`app/(shell)/settings/page.tsx` has a hardcoded `STATIC_AGENT_SLOTS` array
used when the orchestrator is offline. It's missing three agents. Add after
the last entry (AGENT-35-MATHEMATICA or wherever the list ends):

```typescript
{ agentId: "AGENT-39-DEPABS", name: "Dependency Absorption Agent", provider: "anthropic", model: "claude-opus-4-7" },
{ agentId: "AGENT-40-TESTDATA", name: "Database and Test Data Agent", provider: "gemini", model: "gemini-3.1-flash-lite" },
{ agentId: "AGENT-41-RQCA", name: "Runtime QC Agent", provider: "anthropic", model: "claude-sonnet-4-6" },
```

---

## Phase 15 frontend

### New type — `LlmUsageSummary` in `app/lib/types.ts`

```typescript
export type LlmUsageSummary = {
  mission_id: string;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
  estimated_cost_usd: number | null;
  unknown_pricing_count: number;
  call_count: number;
  by_provider: Array<{
    provider: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    estimated_cost_usd: number | null;
  }>;
  by_agent: Array<{
    agent_id: string;
    provider: string;
    model: string;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number | null;
  }>;
};
```

### New API client function — `getMissionTokenUsage`

```typescript
export async function getMissionTokenUsage(
  missionId: string
): Promise<LlmUsageSummary | null> {
  try {
    return await fetchJson<LlmUsageSummary>(
      missionApiUrl(`/v1/missions/${encodeURIComponent(missionId)}/token-usage`),
      { method: "GET" }
    );
  } catch {
    return null;
  }
}
```

### Mission Detail — cost panel

Add `tokenUsage` state loaded from `getMissionTokenUsage(missionId)`.
Render a collapsible "Mission Cost" panel showing:
- Total estimated cost (bold, with "estimate" label)
- Total tokens (input + output)
- Provider/model breakdown table
- Per-agent breakdown table
- Warning badge when `unknown_pricing_count > 0`

---

## Phase 19 frontend

### Extract Mission Detail panels

`missions/[id]/page.tsx` is 1,427 lines. Extract existing panels BEFORE
adding new ones. Create `app/(shell)/missions/[id]/panels/`:

| File | Extracts |
|---|---|
| `EquivalencePanel.tsx` | Equivalence Verification panel |
| `SecurityCompliancePanel.tsx` | Security/Compliance panel |
| `DepAbsPanel.tsx` | Dependency Absorption panel |
| `AimPanel.tsx` | Application Intelligence Map panel |
| `FetchPanel.tsx` | Knowledge Lake (FETCH) panel |
| `MasterLogicStreamPanel.tsx` | Master Logic Stream panel |
| `BuildArtifactsPanel.tsx` | Build Artifacts + Generated Output panels |
| `AuditEvidencePanel.tsx` | Audit Evidence panel |

Each panel: typed props from chain trace, renders nothing (or empty state)
when data is absent.

### Add `ErrorBoundary` component

Create `app/components/error-boundary.tsx`:
```tsx
"use client";
import { Component, type ReactNode } from "react";

type Props = { fallback: ReactNode; children: ReactNode };
type State = { error: boolean };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: false };
  static getDerivedStateFromError() { return { error: true }; }
  render() {
    return this.state.error ? this.props.fallback : this.props.children;
  }
}
```

Wrap every panel in `page.tsx` with:
```tsx
<ErrorBoundary fallback={<p className="muted">Panel data unavailable.</p>}>
  <EquivalencePanel data={equivalenceReport} />
</ErrorBoundary>
```

### PM clarification panel

New type additions to `app/lib/types.ts`:
```typescript
export type PmClarificationState = {
  questions: string[];
  ambiguity_score: number;
  pending: boolean;
};
```

Add to `MissionChainTrace`:
```typescript
pm_clarification?: PmClarificationState | null;
```

Create `app/(shell)/missions/[id]/panels/ClarificationPanel.tsx`:
- Ordered list: each question + textarea
- "Submit Answers" primary button, "Skip" secondary button
- POSTs to `/v1/missions/{id}/pm-clarification` or `.../skip`
- `onResolved()` callback triggers `loadDetails()` refresh

New `api-client.ts` exports:
```typescript
export async function submitPmClarification(missionId: string, answers: string[]): Promise<void>
export async function skipPmClarification(missionId: string): Promise<void>
```

In `page.tsx`, when `mission.state === "PM_CLARIFYING"`:
```tsx
{mission.state === "PM_CLARIFYING" && chainTrace?.pm_clarification?.pending && (
  <ClarificationPanel
    missionId={missionId}
    questions={chainTrace.pm_clarification.questions}
    onResolved={() => void loadDetails()}
  />
)}
```

### Replace `window.confirm` dialogs

Three `window.confirm()` calls in Mission Detail. Replace each with an
inline confirm/cancel state pattern:

```tsx
const [confirmCancel, setConfirmCancel] = useState(false);

// In JSX:
{!confirmCancel ? (
  <button type="button" onClick={() => setConfirmCancel(true)}>
    Cancel Mission
  </button>
) : (
  <div className="inline-confirm" role="alert">
    <span>Confirm cancel? This cannot be undone.</span>
    <button type="button" onClick={() => void cancelMission()}>Yes, cancel</button>
    <button type="button" className="secondary-button"
            onClick={() => setConfirmCancel(false)}>No</button>
  </div>
)}
```

Apply same pattern to Pause Monitor confirm.

---

## Phase 20 frontend

### New types in `app/lib/types.ts`

```typescript
export type VcCommitStrategy = {
  suggested_branch: string;
  commit_message: string;
  files_to_stage: string[];
  rollback_plan: string;
  review_checklist: string[];
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  source: string;
};

export type IntegrationTests = {
  test_code: string;
  test_filename: string;
  test_framework: string;
  test_count: number;
  covers_acceptance_criteria: string[];
  manual_review_items: string[];
  source: string;
  generated_at: string;
};

export type ThreatAnalysis = {
  threat_level: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFORMATIONAL" | "UNKNOWN";
  exploitable: boolean | null;
  exploit_scenario: string | null;
  false_positive_likely: boolean;
  remediation: string;
  block_delivery: boolean;
  source: string;
};

export type DeployReadiness = {
  readiness: "READY" | "READY_WITH_WARNINGS" | "NOT_READY";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  blockers: string[];
  warnings: string[];
  deployment_notes: string;
  suggested_environment: "development" | "staging" | "production";
  source: string;
};
```

Add to `MissionChainTrace`:
```typescript
vc_commit_strategy?: VcCommitStrategy | null;
integration_tests?: IntegrationTests | null;
deploy_readiness?: DeployReadiness | null;
```

Update `SecurityComplianceReport` to include optional `threat_analysis`:
```typescript
threat_analysis?: ThreatAnalysis | null;
```

### New panels

Create in `app/(shell)/missions/[id]/panels/`:

**`VcCommitPanel.tsx`** — shows suggested branch, commit message, rollback
plan, review checklist. Collapsible.

**`IntegrationTestsPanel.tsx`** — shows test count, framework, acceptance
coverage, download button for test file via
`GET /v1/missions/{id}/artifact?artifact_type=integration_tests`.

**`DeployReadinessPanel.tsx`** — color-coded badge (green/amber/red),
deployment notes, suggested environment, blockers list.

### Provider Health panel (Broker)

Add to the Agents page sidebar or AGENT-03-BROKER agent card: a "Provider
Health" mini-panel fetched from `GET /internal/broker/provider-health`.

New API client function:
```typescript
export async function getBrokerProviderHealth(): Promise<Record<string, {
  call_count_5min: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  error_count_total: number;
}> | null>
```

---

## Phase 21 frontend

### New types

```typescript
export type PodAuditVerdict = {
  verdict: "PASS" | "PARTIAL" | "FAIL";
  coverage_score: number | null;
  intent_quality_score: number | null;
  findings: string[];
  missing_domains: string[];
  weak_intents: string[];
  blocking: boolean;
  summary: string;
  total_nodes_reviewed: number;
  source: string;
};
```

Add to `MissionChainTrace`:
```typescript
pod_audit_verdict?: PodAuditVerdict | null;
```

### New panel

**`PodAuditPanel.tsx`** — verdict chip (green/amber/red), coverage score
progress bar, missing domains list, weak intents list.

---

## Phase 22 frontend

### New types

```typescript
export type TestdataManifest = {
  base_image: string;
  install_commands: string[];
  env_vars: Record<string, string>;
  synthetic_inputs: Array<{ input_id: string; description: string; input_data: string }>;
  run_command: string;
  timeout_seconds: number;
  memory_limit_mb: number;
  network_required: boolean;
  notes: string;
  language: string;
  test_framework: string;
  source: string;
};

export type RuntimeQcReport = {
  verdict: "PASS" | "FAIL" | "TIMEOUT" | "ERROR" | "DRY_RUN" | "SKIPPED";
  passed: boolean;
  execution_type: "docker_live" | "dry_run" | "skipped";
  exit_code?: number | null;
  expected_exit_code?: number;
  stdout_preview?: string;
  stderr_preview?: string;
  base_image?: string;
  language: string;
  filename: string;
  timeout_seconds?: number;
  dry_run_reason?: string;
  qc_assessment?: {
    qc_verdict: "PASS" | "WARN" | "FAIL" | "INCONCLUSIVE" | "ADVISORY";
    confidence: "HIGH" | "MEDIUM" | "LOW";
    findings: string[];
    remediation: string[];
    deployment_safe: boolean;
    source: string;
  } | null;
  source: string;
};
```

Add to `MissionChainTrace`:
```typescript
testdata_manifest?: TestdataManifest | null;
runtime_qc_report?: RuntimeQcReport | null;
```

### New panels

**`RuntimeQcPanel.tsx`** — execution verdict chip (green/amber/red/grey),
QC verdict, execution type badge ("live" vs "dry run" vs "skipped"),
stdout preview (truncated, monospace), findings list, remediation list.

**`TestEnvironmentPanel.tsx`** — collapsible, shows base image, install
commands, run command, synthetic input count, timeout/memory limits.

---

## Phase 23 frontend

### New types

```typescript
export type SbomDelta = {
  original_dependency_count: number;
  removed: string[];
  remaining: string[];
  kept_with_justification: string[];
  reduction_percent: number;
};
```

Add to `MissionChainTrace`:
```typescript
sbom_delta?: SbomDelta | null;
depabs_execution?: {
  status: string;
  absorption_count: number;
  splices: Array<{ library: string; symbols_replaced: string[]; status: string }>;
} | null;
```

### New panel

**`SbomDeltaPanel.tsx`** — prominent `reduction_percent` metric, removed
dependencies chip list (green), remaining chip list, kept-with-justification
list.

---

## Phase 24 frontend

### New types

Add to `MissionChainTrace`:
```typescript
port_phase?: "extraction" | "generation" | null;
port_source_language?: string | null;
port_target_language?: string | null;
port_source_logicnodes?: Array<{ domain: string; concept: string; intent: string }> | null;
```

### PORT phase indicator

In `page.tsx`, for PORT missions, render a two-step progress indicator
above the normal phase stepper:

```tsx
{metadata?.mission_type === "PORT" && chainTrace?.port_source_language && (
  <div className="port-phase-indicator" aria-label="PORT mission progress">
    <span className={chainTrace.port_source_logicnodes ? "complete" : "active"}>
      EXTRACTION: {chainTrace.port_source_language}
      {chainTrace.port_source_logicnodes ? " ✓" : " ●"}
    </span>
    <span className="arrow">→</span>
    <span className={chainTrace.port_source_logicnodes ? "active" : "pending"}>
      GENERATION: {chainTrace.port_target_language ?? mission.requested_target_language}
      {mission.state === "COMPLETE" ? " ✓" : ""}
    </span>
  </div>
)}
```

---

## Phase 25 frontend

### Prompt registry panel (admin only)

Add a "Prompt Registry" section to the Settings page showing the list from
`GET /internal/prompt-registry`:

```typescript
export async function getPromptRegistry(): Promise<Array<{
  prompt_id: string;
  version: string;
  owner_agent_id: string;
  sha256: string;
  created_at: string;
  change_note: string;
}> | null>
```

Show as a simple table. Admin-key only — gate behind vault session check.

---

## Phase 26 frontend

No new panels. Phase 26 is backend-only (git scrub, DR drill, qualification
evidence). The settings page should show vault status clearly before this
phase, but no new UI components are required.

---

## Phase 27 frontend — final convergence checklist

All 12 evidence panels added in Phases 19–25 must be verified against live
data and against absent data (empty state). See Phase 27 plan for the full
audit table.

Additional Phase 27 items:
- [ ] Lighthouse performance ≥ 85 on Mission Detail page (new panels may
      regress this — audit after all panels land)
- [ ] Accessibility: all new panels have `role`, `aria-label`, keyboard nav
- [ ] E2E specs for each new mission outcome (see Phase 27 plan)
- [ ] `README.md` quick start demo accurate and functional
- [ ] No `window.confirm` calls remaining in the codebase
- [ ] Mission Detail `page.tsx` reduced to ≤ 600 lines after panel extraction

---

## Validation (cumulative — all items must pass before Phase 27 ships)

### TypeScript
- [ ] `npm run lint` — 0 errors (after cache clear)
- [ ] `null` safety fix applied in `repo/review/route.ts`
- [ ] All new types added without `any` escapes

### New components
- [ ] `ErrorBoundary` component exists and wraps all Mission Detail panels
- [ ] `ClarificationPanel` renders and submits correctly
- [ ] All Phase 20–24 panels render with data and empty states
- [ ] No `window.confirm` calls remain

### API client
- [ ] `getMissionTokenUsage`, `submitPmClarification`, `skipPmClarification`,
      `getBrokerProviderHealth`, `getPromptRegistry` all exported
- [ ] All return `null` on 404/network failure (never throw to the UI)

### Settings
- [ ] AGENT-39, AGENT-40, AGENT-41 in `STATIC_AGENT_SLOTS`
- [ ] Vault slots table shows 41 rows offline

### Tests
- [ ] `npm test` green with new panel unit tests
- [ ] New E2E specs in `e2e/` pass against mock fixtures
