# Phase 15 — Token and Cost Ledger (UPDATED)

**Status:** Planned (current active phase)
**Last updated:** 2026-05-18
**Updated:** Frontend pre-work added — lint must be green before this phase ships.
**Depends on:** Phase 1 model governance, Phase 10 delivery, Phase 11 AIM, Phase 14 dependency absorption

---

## Pre-work: Fix TypeScript lint (do before any Phase 15 code)

`npm run lint` is currently red. All failures are in `lint_errors.txt`.
Fix these before writing any Phase 15 code so the CI gate stays meaningful.

### Fix 1 — Clear stale build cache

The `listMissions`, `getMission`, `getMissionEvents` "no exported member"
errors are false — the functions exist in `api-client.ts`. They are caused
by a stale `.tsbuildinfo` incremental build cache.

```bash
cd apps/mission-control
rm -rf .next tsconfig.tsbuildinfo
npm run lint
```

Expected: those three errors disappear. Verify before proceeding.

### Fix 2 — `LARGE_FILE_BYTES` not found in `app/api/repo/import/route.ts`

`LARGE_FILE_BYTES` is exported from `app/api/repo/shared.ts` line 32.
The import in `app/api/repo/import/route.ts` is correct. This is also
a cache artifact — resolves with the cache clear above. If it persists
after cache clear, verify the import path resolves to the correct file.

### Fix 3 — `null` not assignable to `string` in `app/api/repo/review/route.ts`

Location: line 543 — `params.requestedTargetLanguage` is `string | null`
but passed to a function expecting `string`.

Fix:
```typescript
// Before:
!testPlan.some((step) => step.toLowerCase().includes(params.requestedTargetLanguage!))

// After:
!testPlan.some((step) =>
  step.toLowerCase().includes(params.requestedTargetLanguage ?? "")
)
```

Remove the `!` non-null assertion. Use `?? ""` fallback instead.
TypeScript 6 is stricter about `!` — this needs a proper null guard.

### Fix 4 — Implicit `any` on filter callback in `missions/[id]/page.tsx` line 99

Location: `agentSnapshot.agents.filter((agent: OperationsAgentRecord) => ...)`.
The explicit type annotation is correct but TypeScript 6 may still flag it
if `agentSnapshot` is inferred as `any` at the call site. Check that
`getOperationsAgents()` return type is properly resolved after cache clear.
If the error persists, change the destructured call to:

```typescript
const agentSnapshotData = await getOperationsAgents({ ... });
setActiveAgents(
  agentSnapshotData.agents.filter((agent: OperationsAgentRecord) =>
    isAgentActive(agent, missionId)
  )
);
```

### Verification

```bash
cd apps/mission-control
rm -rf .next tsconfig.tsbuildinfo
npm run lint    # Must be 0 errors
npm test        # Must be green
```

Do not start Phase 15 backend work until both are green.

---

## Validated Entry State

[... remainder of Phase 15 plan unchanged — see Phase_15_Token_Cost_Ledger.md ...]

## Updated Implementation Plan

1. Add the durable ledger schema.
2. Normalize usage from every provider.
3. Wrap the actual LLM call boundary.
4. Add cost estimation.
5. Expose mission summaries.
6. Add budget controls and warnings.
7. Render Mission Control cost evidence.

See `Phase_15_Token_Cost_Ledger.md` for full implementation details.

## Frontend additions for Phase 15

### New type in `app/lib/types.ts`

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

### New API client function

Add to `app/lib/api-client.ts`:
```typescript
export async function getMissionTokenUsage(missionId: string): Promise<LlmUsageSummary | null> {
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

### Settings page — add agents 39–41 to STATIC_AGENT_SLOTS

In `app/(shell)/settings/page.tsx`, the `STATIC_AGENT_SLOTS` array is
missing three agents. Add after the last entry:

```typescript
  { agentId: "AGENT-39-DEPABS", name: "Dependency Absorption Agent", provider: "anthropic", model: "claude-opus-4-7" },
  { agentId: "AGENT-40-TESTDATA", name: "Database and Test Data Agent", provider: "gemini", model: "gemini-3.1-flash-lite" },
  { agentId: "AGENT-41-RQCA", name: "Runtime QC Agent", provider: "anthropic", model: "claude-sonnet-4-6" },
```

## Validation

- [ ] `npm run lint` — 0 errors (after cache clear and fixes above)
- [ ] `npm test` — all 55 tests green
- [ ] `getMissionTokenUsage` added to `api-client.ts`
- [ ] `LlmUsageSummary` type added to `types.ts`
- [ ] AGENT-39/40/41 added to `STATIC_AGENT_SLOTS` in settings page
- [ ] Mission Detail cost panel renders for a COMPLETE mission
- [ ] Cost tracking failure does not break mission flow
- [ ] Backend tests green
