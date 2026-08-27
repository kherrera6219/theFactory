# Repo ZIP Phases 5–7 — Source Verification (2026-08-21)

Document version: 2026.08.21
Last updated: 2026-08-21
Status: Evidence / status reconciliation — **UI trigger seam closed**
Audience: Maintainers and coding agents

## Purpose

Reconcile `docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md`, `docs/WORK_QUEUE.md` item #8,
and live source. Prior status text treated Phases 5–7 as fully open. That was
wrong for the backend; the launch-path wiring is also present in source.

## Method

Read-only inspection of `main` (file/function evidence below). No live mission
was run in the original 2026-08-21 pass; UI wiring was confirmed on re-read the
same day.

## Verified — implemented in code

### Phase 5 — Mission launch index guard

**Verified** in `services/orchestrator/orchestrator/mission_flow_v2/phases_intake.py`
(`_prepare_pm_intake`):

- Reads `metadata.repo_import`
- If `index_required` is true and `index_status` is not `complete`, appends
  `REPO_INDEX_PENDING` (once) and returns `False` (mission stays queued)
- Tests exist in `tests/services/test_mission_flow_v2.py`:
  - pending does not advance to PM contract generation
  - duplicate `REPO_INDEX_PENDING` is not appended on re-entry

### Phase 6 — Repo knowledge ingestion

**Verified** Mission Control route:

- `apps/mission-control/app/api/repo/index/route.ts`
- Builds bounded `repo_manifest` / `repo_summary` / `repo_source_chunk` records
  from reviewed file excerpts (caps: 200 files, 2000 chars/chunk)
- POSTs to orchestrator
  `/internal/missions/{mission_id}/repo-import-index` with internal service key
- Unit tests: `apps/mission-control/app/api/repo/index/route.test.ts`

**Verified** orchestrator endpoint:

- `services/orchestrator/orchestrator/routes/internal.py`
  → `POST /internal/missions/{mission_id}/repo-import-index`
  → `upsert_repo_import_index`
- Writes knowledge rows; updates `metadata.repo_import.index_status`
- On `index_status == "complete"`, calls `start_lifecycle_task` to resume
  the Phase 5–blocked queued mission
- Emits `MISSION_REPO_INDEX_COMPLETE` audit event

### Phase 7 — Agent context wiring

**Verified** PM intake:

- `load_repo_context()` in `phases_intake.py`
- Loads `repo_manifest`, `repo_summary`, up to 20 `repo_source_chunk` rows
- Merges into ≤6000-char block; injects
  `conversation_context["repository_context"]` when present

**Verified** pod-worker:

- `services/pod-worker/pod_worker/main.py` → `_fetch_doc_context`
- Includes `bootstrap_documentation` (language-filtered),
  `repo_summary` (all specialists), and up to 10 `repo_source_chunk` records

### UI trigger seam (WORK_QUEUE #8)

**Verified** end-to-end operator path in Chat:

1. `apps/mission-control/app/lib/chat-repo-import.ts`
   - `buildRepoImportLaunchMetadata(review)` → compact `metadata.repo_import`
     (`index_required: true`, `index_status: "pending"`)
   - `buildRepoIndexRequest(missionId, review)` → POST body for `/api/repo/index`
   - Unit tests in `chat-repo-import.test.ts` cover both helpers

2. `apps/mission-control/app/(shell)/chat/page.tsx` `confirmAndLaunch`:
   - When `repoImportRef.current` is set, `fitConversationContext` metadata
     includes `repo_import` with `index_required: true` / `index_status: "pending"`
   - After `createMission` returns, calls `indexRepoImport(...)` with the
     reviewed text-available file excerpts
   - Index failure is non-fatal to mission creation but surfaces a warning that
     PM intake may stay paused until indexing succeeds

3. Repo page still hands off via sessionStorage (`REPO_HANDOFF_STORAGE_KEY`);
   Chat consumes the handoff, sets `repoImportRef`, and the launch path above
   arms Phase 5 + triggers Phase 6.

Consequence: Phase 5 guard arms on ZIP/repo launches; Phase 6 is called from
the operator path; Phase 7 loaders can find repo knowledge rows once index
completes.

## Remaining optional polish (not blocking #8)

- Surface index status (`pending` → `complete` / error) more visibly in Chat/Repo UI
- Live end-to-end ZIP→index→PM proof under `LIVE_STACK_REQUIRED=1` (not run in
  this verification pass)
- Extracted-folder / “Open Folder” UI remains a separate operator convenience

## Non-goals for this note

- No claim of live runtime of the closed loop in the original session
- Electron packaging and BUILD_NEW equivalence remain separate open items

## Confidence

- **High** on backend Phase 5–7 presence (file/function evidence above)
- **High** on UI `repo_import` + post-create index call (direct page + helper read)
- **N/A** on live runtime of the closed loop in this session
