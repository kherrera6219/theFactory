# Repo ZIP Phases 5–7 — Source Verification (2026-08-21)

Document version: 2026.08.21
Last updated: 2026-08-21
Status: Evidence / status reconciliation
Audience: Maintainers and coding agents

## Purpose

Reconcile `docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md`, `docs/WORK_QUEUE.md` item #8,
and live source. Prior status text treated Phases 5–7 as fully open. That was
wrong for the backend; the remaining gap is launch-path wiring.

## Method

Read-only inspection of `main` at SHA `ce9e04234b3dd7aaaaceb94fda84767da2c42df5`
(and contemporaneous file contents). No live mission was run in this pass.

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

## Verified — not wired end-to-end

### Launch path does not arm or trigger indexing

**Verified** gaps:

1. `apps/mission-control/app/(shell)/repo/page.tsx` `launchRepoMission()` only
   writes a session handoff (`REPO_HANDOFF_STORAGE_KEY`) and navigates to
   `/chat?fromRepo=1`. It does **not** create a mission and does **not** call
   `POST /api/repo/index`.

2. `apps/mission-control/app/lib/chat-repo-import.ts` handoff shape carries
   `review` + `approval` only. There is no `repo_import` block
   (`import_id`, `archive_sha256`, `index_required`, `index_status`).

3. Repo-wide TypeScript search for `repo_import` / `index_required` under
   `apps/mission-control` returned **no** application usages outside the
   Phase 6 index route itself. Mission create from Chat therefore does not
   set `metadata.repo_import.index_required=true`.

Consequence: Phase 5 guard never arms; Phase 6 endpoint is never called from
the operator path; Phase 7 loaders find no repo knowledge rows. Backend is
ready; the product path is still “approved source bundle only.”

## What is still owed (implementation slice)

Do not reopen Phases 5–7 backend. Close the **UI trigger seam**:

1. Extend handoff / Chat launch metadata with compact:

   ```json
   {
     "repo_import": {
       "import_id": "repozip-…",
       "archive_sha256": "…",
       "display_name": "…",
       "source_ref": "…",
       "index_required": true,
       "index_status": "pending"
     }
   }
   ```

2. After `createMission` returns a `mission_id` for a repo/ZIP handoff, call
   `POST /api/repo/index` with `mission_id`, `import_id`, `archive_sha256`,
   and the reviewed file excerpts already held in the handoff/review object.

3. Surface index status in Chat/Repo UI (`pending` → `complete` / error).

4. Tests:
   - unit: handoff carries `repo_import` and Chat post-create calls index
   - optional integration: pending mission stays queued until index complete,
     then PM receives `repository_context`

5. Update `docs/REPO_ZIP_IMPORT_MIGRATION_PLAN.md` phase statuses and
   `docs/WORK_QUEUE.md` item #8 after the wiring lands and is test-green.

## Non-goals for this note

- No application code change in this commit
- No claim of live end-to-end ZIP→index→PM proof (not run here)
- Electron packaging and BUILD_NEW equivalence remain separate open items

## Confidence

- **High** on backend Phase 5–7 presence (file/function evidence above)
- **High** on missing UI `repo_import` / index call (negative search + page read)
- **N/A** on live runtime of the closed loop in this session
