# User Story, Journey, and Interaction Review (Production Standard)

Date: March 1, 2026  
Repo: `C:\software\Holygrail\theFactory`  
Primary surface reviewed: `apps/mission-control` + gateway/orchestrator mission APIs

## 1. Findings First (Severity Ranked)

### High

1. Missing end-to-end user journey elements required by product docs.
- Evidence:
  - UI supports mission submission and single mission status only: `apps/mission-control/app/page.tsx`.
  - No account context, no "My Missions" list, no confirmation messaging channel.
  - Internal acceptance criteria expects "My Missions" visibility and confirmation steps: `C:\software\Holygrail\61_User_Stories_Use_Cases.md` lines 660-669.
- Risk:
  - Users cannot reliably continue, resume, or manage work across sessions.
  - Journey breaks after first mission for production operations.

2. Failure recovery UX is weak for runtime/polling failures.
- Evidence:
  - Polling failures are swallowed silently in `page.tsx` lines 85-87.
  - Submission error text is generic (`intake failed: <status>`) in `page.tsx` lines 51-53.
  - Interaction guide expects explicit "what happened / what you can do" recovery patterns: `C:\software\Holygrail\62_User_Interaction_Guide.md` lines 549-573.
- Risk:
  - Users get stalled without actionable next steps, increasing retry loops and support load.

3. Accessibility gap for dynamic status changes (screen-reader users).
- Evidence:
  - No `aria-live` status/alert regions in dynamic mission state and event updates (`page.tsx` lines 135-177).
  - Internal guide explicitly requires live status/alert examples: `62_User_Interaction_Guide.md` lines 607-614.
- Risk:
  - Live mission progress is not announced to assistive technology users.
  - Fails production-grade inclusive UX expectations.

### Medium

4. Mission submission path does not use idempotency header from UI.
- Evidence:
  - UI POST includes only `Content-Type` header (`page.tsx` lines 41-43).
  - API gateway supports `Idempotency-Key` (`services/api-gateway/api_gateway/main.py` lines 377-480).
- Risk:
  - Duplicate missions from fast retries/double clicks/network retries.

5. Progress communication is minimal (no ETA/progress percent).
- Evidence:
  - UI shows state and timeline only (`page.tsx` lines 135-177).
  - Product docs expect estimated completion and richer progress context (`61_User_Stories_Use_Cases.md` lines 704-713, `62_User_Interaction_Guide.md` lines 109-121).
- Risk:
  - Low confidence during long-running jobs; users may abandon or resubmit.

6. Journey depends on polling only; no explicit polling health indicator.
- Evidence:
  - 2.5s polling loop exists (`page.tsx` lines 70-90), but no "disconnected/stale data" indicator.
- Risk:
  - Users cannot distinguish "mission idle" vs "UI stopped updating."

### Low

7. No skip link or explicit quick-jump accessibility affordance.
- Evidence:
  - Layout only renders children (`apps/mission-control/app/layout.tsx` lines 22-26).
- Risk:
  - Keyboard efficiency and accessibility are lower than production best practice.

8. Validation guidance is limited for the mission prompt field.
- Evidence:
  - Prompt min length enforced (`required`, button disabled under 3 chars) but no helper/error guidance (`page.tsx` lines 107-114, 129-131).
- Risk:
  - Minor input confusion and avoidable retries.

## 2. Standards Used (External + Internal)

### External standards and guidance used
- ISO 9241-210 (human-centered design lifecycle principles).
- WCAG 2.2 (perceivable/operable/understandable/robust accessibility baseline).
- WAI-ARIA Authoring Practices (status/alert pattern expectations for dynamic updates).
- Nielsen heuristic framework and heuristic evaluation method (system status, error recovery, consistency, etc.).
- Agile INVEST quality criteria for user stories.
- GOV.UK service journey mapping practice ("map the whole problem" across channels and stages).

### Internal product standards used
- `C:\software\Holygrail\61_User_Stories_Use_Cases.md`
- `C:\software\Holygrail\62_User_Interaction_Guide.md`
- `C:\software\Holygrail\15_Mission_Control_UI_Specification.md`

## 3. How the Review Was Conducted

1. Reviewed product intent and acceptance criteria from Documents 61/62/15.
2. Performed implementation review on mission-control UI and mission lifecycle APIs.
3. Ran task walkthrough in live local stack:
   - `GET /health`, `GET /readyz`
   - `POST /v1/missions`
   - `GET /v1/missions/{id}`
   - `GET /v1/missions/{id}/events`
4. Assessed interaction behavior against heuristics + accessibility expectations.
5. Mapped findings to production-risk severity and remediation plan.

## 4. Observed Walkthrough Evidence (Live)

Environment: local stack running via Docker on March 1, 2026.

- Health/readiness:
  - API gateway health returned `ok: true`.
  - API gateway readiness returned ready.
- Mission flow:
  - Mission created successfully and returned mission id.
  - Mission reached `VERIFIED`, then event stream showed transition sequence:
    - `MISSION_QUEUED`
    - `MISSION_RUNNING`
    - `MISSION_VERIFIED`
    - `MISSION_COMPLETE`
- Submission performance sample (5 requests):
  - `70.3ms, 6.09ms, 4.16ms, 4.5ms, 4.21ms`
  - Average: `17.85ms` (comfortably within internal "<=2s" target for intake acceptance).

## 5. User Story Review (Production Quality)

Current implementation supports a narrow core story:
- "As a user, I can submit one mission and see current state."

Against INVEST:
- `I` Independent: Partial (status depends on backend readiness).
- `N` Negotiable: Partial (hard-coded target language set and fixed UI flow).
- `V` Valuable: Pass (core value exists).
- `E` Estimable: Pass (clear transaction boundaries).
- `S` Small: Pass.
- `T` Testable: Partial (happy path is testable; failure/accessibility criteria are weak).

Recommended production user stories to add now:

1. Mission continuity story.
- As an authenticated user, I can view my active and recent missions so I can resume work.
- Acceptance criteria:
  - Mission list visible after submit and on reload.
  - Filter by state.
  - Selecting a mission restores timeline/details.

2. Resilient status story.
- As a mission owner, I can see live status and clear stale/offline indicators.
- Acceptance criteria:
  - UI displays "Live", "Retrying", or "Disconnected" status.
  - Poll failures surface actionable guidance within 5 seconds.

3. Failure recovery story.
- As a user, I get human-readable error causes and next actions.
- Acceptance criteria:
  - Errors include context and recommended action.
  - Retry path is one click.
  - Support/debug info is available without exposing sensitive internals.

4. Accessibility story.
- As a keyboard/screen-reader user, I can submit and track missions with equivalent usability.
- Acceptance criteria:
  - Dynamic updates announced via `aria-live`.
  - Error alerts use assertive announcement.
  - Keyboard-only flow is complete with visible focus and skip navigation.

## 6. User Journey Review

### Current implemented journey
1. User enters mission prompt and target language.
2. User submits mission.
3. UI shows mission status and event timeline via polling.

### Missing production journey segments
1. Pre-submit trust/orientation (scope, expectations, estimated runtime guidance).
2. Multi-mission management and return visits.
3. Failure branch with clear remediation actions.
4. Completion branch with export/share/follow-up actions.

## 7. Interaction Heuristic Review (Summary)

- Visibility of system status: `Partial`  
  Current state exists, but no explicit connection health or ETA.

- Match between system and real world: `Partial`  
  Lifecycle states are technical (`INTAKE`, `VERIFIED`) with limited user-facing translation.

- User control and freedom: `Partial`  
  No cancel/pause or mission-switch control in UI.

- Consistency and standards: `Pass`  
  UI labels and structure are internally consistent.

- Error prevention: `Partial`  
  Prompt minimum and disabled submit are present; duplicate-submission prevention missing at client level.

- Recognition rather than recall: `Partial`  
  Single mission context only; no mission history or saved context.

- Flexibility and efficiency: `Partial`  
  Works for first-time users, limited for power users.

- Aesthetic/minimalist design: `Pass`  
  Clear and focused layout.

- Help users recover from errors: `Fail`  
  Silent polling failure and generic intake errors.

- Help and documentation: `Partial`  
  Basic interface text present, no in-app contextual guidance.

## 8. Production Remediation Plan

### Phase 1 (Immediate, 1-2 sprints)
1. Add explicit error/retry UX for submission and polling failures.
2. Add `aria-live` regions for mission status and alert announcements.
3. Send `Idempotency-Key` from UI for mission creation.
4. Add polling health indicator (`live`, `retrying`, `stale`).

### Phase 2 (Near-term, 2-4 sprints)
1. Add mission history ("My Missions") and mission detail re-entry flow.
2. Add user-facing progress model (percent/ETA once available from backend).
3. Add guided empty states and helper text for submission inputs.

### Phase 3 (Production readiness validation)
1. Run moderated journey tests with representative personas from Doc 61.
2. Run accessibility audit to WCAG 2.2 AA with automated + manual checks.
3. Define and verify UX SLOs:
   - Mission submit success rate.
   - Median and p95 submit latency.
   - Polling freshness target.
   - Error recovery success rate.

## 9. Exit Criteria for Production Sign-Off

1. All High findings resolved and regression-tested.
2. WCAG 2.2 AA criteria met for tracked mission workflows.
3. Journey completeness:
   - Submit mission
   - Track live progress
   - Recover from failure
   - Resume prior mission
4. User story acceptance criteria captured in CI/QA checks.
5. Observability includes UX-impacting signals (frontend errors, stale polling, submit retries).

## 10. External References

- WCAG 2.2: https://www.w3.org/TR/WCAG22/
- WAI-ARIA APG: https://www.w3.org/WAI/ARIA/apg/
- ISO 9241-210 overview: https://www.iso.org/standard/77520.html
- NNGroup heuristics: https://www.nngroup.com/articles/ten-usability-heuristics/
- NNGroup heuristic evaluation method: https://www.nngroup.com/articles/how-to-conduct-a-heuristic-evaluation/
- Agile INVEST (user stories): https://agilealliance.org/glossary/invest/
- GOV.UK journey mapping guidance: https://www.gov.uk/service-manual/user-research/map-the-whole-problem
