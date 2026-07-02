# Repository ZIP Import Migration Plan

Document version: 2026.07.02
Last updated: 2026-07-02
Status: Active
Audience: Operators, developers, maintainers, and auditors

## Purpose

Replace Mission Control's current GitHub API based repository import workflow with a local repository ZIP import workflow. The goal is to let operators import a source snapshot from a local `.zip` file, review selected files, apply the existing review gate, and launch missions without requiring GitHub network access or a GitHub token.

## Current System Review

The current Mission Control repository flow is implemented in the desktop/web app under `apps/mission-control/app`.

- UI entrypoint: `apps/mission-control/app/(shell)/repo/page.tsx`
- Import endpoint: `apps/mission-control/app/api/repo/import/route.ts`
- Review endpoint: `apps/mission-control/app/api/repo/review/route.ts`
- Shared GitHub helpers: `apps/mission-control/app/api/repo/shared.ts`
- Client wrapper: `apps/mission-control/app/lib/api-client.ts`
- Types: `apps/mission-control/app/lib/types/api.ts`
- Tests: `apps/mission-control/app/api/repo/import/route.test.ts` and `apps/mission-control/app/api/repo/review/route.test.ts`

Current import behavior:

1. The UI accepts a `https://github.com/<owner>/<repo>` URL, branch, subdirectory, and max file count.
2. `POST /api/repo/import` parses the GitHub URL, resolves repository metadata through `https://api.github.com/repos/{owner}/{repo}`, then fetches a recursive tree through `git/trees/{branch}?recursive=1`.
3. The endpoint returns metadata plus a filtered/sorted file list. Large files over `1_500_000` bytes are skipped.
4. The operator selects include/reference/exclude overlays.
5. `POST /api/repo/review` re-fetches selected file contents through the GitHub contents API and raw API, builds a source bundle, computes a review fingerprint, and returns a review artifact.
6. The existing approval and mission launch flow sends the generated source bundle into mission creation.

Important current gap:

- The repo page has an Electron local-directory browse button that sets `file://...`, with an inline comment saying the backend accepts local repos. That is not true today. The import and review endpoints reject anything other than `https://github.com/...`.

## External Research Notes

GitHub source ZIP files are source snapshots, not full clones. GitHub documents that source archives can be downloaded for branches, tags, or commits, and they do not include full repository history. GitHub also documents that branch/tag archive contents can change when the ref moves, while commit-SHA archives give stable extracted contents as long as the commit remains available. For private repository archive API redirects, GitHub notes that archive links are temporary.

For local ZIP processing, Python's `zipfile` documentation explicitly warns not to extract untrusted archives without inspection because path traversal and absolute paths can create files outside the intended destination. The same class of issue applies in Node implementations: Mission Control should inspect archive entries and stream file content from the archive rather than blindly extracting to the app filesystem.

Planning consequences:

- Treat ZIP input as an untrusted source package.
- Prefer archive inspection and selective reading over whole-archive extraction.
- Normalize GitHub-generated ZIP roots such as `<repo>-<sha>/`, but also support plain ZIP files whose files live at archive root.
- Preserve reproducibility metadata when available: uploaded filename, archive hash, inferred root prefix, and optional operator-entered source ref.
- Do not promise full Git history, submodule checkout, or Git LFS hydration from a ZIP snapshot.

References:

- GitHub source archive docs: `https://docs.github.com/en/repositories/working-with-files/using-files/downloading-source-code-archives`
- GitHub archive REST docs: `https://docs.github.com/en/rest/repos/contents?apiVersion=2022-11-28#download-a-repository-archive-zip`
- Python ZIP extraction warning: `https://docs.python.org/3/library/zipfile.html#zipfile.ZipFile.extractall`

## Target User Flow

1. Operator opens `Repo Import`.
2. Step 1 becomes `Import Repository ZIP`.
3. In Electron, the primary control opens a native file picker filtered to `.zip`. In a browser build, the primary control is an `<input type="file" accept=".zip,application/zip">`.
4. Operator optionally enters:
   - display repository name
   - source ref or commit SHA
   - subdirectory
   - max files
5. UI posts the ZIP file and options as `multipart/form-data` to `POST /api/repo/import`.
6. Backend validates and indexes the ZIP entries, returns safe file metadata and archive metadata.
7. Operator selects file overlays exactly as today.
8. UI calls `POST /api/repo/review` with an archive import token or archive ID plus selected file metadata.
9. Backend reads selected file bodies from the staged archive/index, builds the same review artifact shape as today, and the existing review gate plus mission launch flow continues unchanged.

## Proposed API Contract

### `POST /api/repo/import`

Change from JSON to multipart form data.

Fields:

- `archive`: required ZIP file.
- `display_name`: optional user-facing name.
- `source_ref`: optional branch/tag/commit label entered by the operator.
- `subdirectory`: optional path, default `/`.
- `max_files`: optional number, keep current clamping behavior.

Response:

```json
{
  "repository": {
    "source": "zip",
    "display_name": "sample-platform",
    "archive_id": "repo-zip-...",
    "archive_sha256": "...",
    "source_ref": "main",
    "root_prefix": "sample-platform-main/",
    "html_url": null
  },
  "files": [
    {
      "path": "apps/web/page.tsx",
      "language": "TypeScript",
      "bytes": 1200,
      "estimated_lines": 27
    }
  ],
  "stats": {
    "total_files": 300,
    "estimated_total_lines": 12000,
    "selected_subdirectory": "/",
    "truncated": false,
    "skipped_large_files": 2,
    "skipped_unsafe_entries": 0
  },
  "logs": []
}
```

### `POST /api/repo/review`

Implemented status: this route currently accepts multipart form data so the
same uploaded ZIP can be hash-bound and re-read during review. A future staged
archive implementation can move this contract to `archive_id` plus
`archive_sha256` without a second upload.

Fields:

- `source`: `"zip"`
- `archive_id`: required
- `archive_sha256`: required, used as an integrity guard
- `display_name`: optional
- `source_ref`: optional
- `subdirectory`: optional
- `mission_type`: unchanged
- `description`: unchanged
- `selected_files`: unchanged shape

The response should preserve the current `RepoReviewResponse` shape where possible. Change `repository` metadata to support `source: "zip"`, `display_name`, `archive_sha256`, `source_ref`, and `selected_subdirectory`. Keep `review_fingerprint`, `source_code`, `files`, `plan`, `risk_notes`, and `test_plan` stable so approval and launch do not need large rewrites.

## Backend Design

Add a ZIP import module under `apps/mission-control/app/api/repo`:

- `archive.ts` or `zip-shared.ts`
- `parseRepoZipUpload(formData)`
- `indexZipArchive(fileOrBuffer, options)`
- `normalizeArchivePath(entryName, rootPrefix)`
- `detectCommonRootPrefix(entries)`
- `safeRepoPath(entryName)`
- `readZipTextFile(archiveId, path)`

Implementation requirements:

- Use a maintained ZIP reader that supports entry listing and selective streaming in Node.js. `yauzl` is a good fit because it can lazily read entries without extracting the full archive. `adm-zip` is simpler but tends to read archives eagerly; avoid it for large/untrusted inputs.
- Store uploads in an app-controlled temp/import directory with generated IDs. In Electron/local runtime, this can be under Mission Control local app data or a configured workspace cache.
- Never extract the full archive by default.
- Reject or skip entries with absolute paths, drive letters, UNC prefixes, `..` traversal, empty path segments, null bytes, backslash-only paths, or directory entries.
- Normalize `/` separators and strip one common generated root prefix.
- Enforce limits before review:
  - max compressed upload size
  - max total uncompressed bytes
  - max entry count
  - max single-file bytes, reusing `LARGE_FILE_BYTES`
  - max selected review files, reusing `MAX_SELECTED_FILES`
  - allowed text encodings or UTF-8 decode with replacement plus binary detection
- Compute and persist `sha256` for the uploaded archive.
- Compute per-entry metadata from central-directory data when possible.
- Read selected file contents only during review and only for include/reference files.
- Expire staged archives after a bounded time or when the mission is launched, unless an operator explicitly saves the source package.

## Frontend Design

Update `apps/mission-control/app/(shell)/repo/page.tsx`:

- Rename page framing from `GitHub Import` to `Repository ZIP Import`.
- Replace the GitHub URL input with a ZIP file selector.
- In Electron, use `electronShowOpenDialog` with:
  - `properties: ["openFile"]`
  - `filters: [{ name: "Repository ZIP", extensions: ["zip"] }]`
- In browser mode, use a normal file input and submit the selected `File`.
- Keep branch field only as an optional `Source ref` text input. Do not imply the app resolves a branch.
- Keep subdirectory and max files.
- Preserve Step 2 file overlay UI, Step 3 review gate, and Step 4 mission launch.
- Store `archive_id`, `archive_sha256`, and ZIP metadata in component state after import.
- Ensure `resetReviewGate()` runs whenever a new ZIP, source ref, subdirectory, or selected file overlay changes.
- Update launch mission metadata:
  - `source: "repo-zip-import-ui"`
  - `archive_id`
  - `archive_sha256`
  - `source_ref`
  - `repository_name` or `display_name`
  - remove GitHub-only fields or keep them null.

Update navigation copy:

- `apps/mission-control/app/lib/navigation.ts`: change `Repo Import` description from GitHub import to local ZIP import.

Update settings:

- The GitHub PAT setting can remain for other future integrations, but the repo ZIP import page should no longer require it or surface GitHub rate-limit errors.

## Live UI Impact Review

Historical pre-migration baseline: before Phase 4, the running page at
`http://localhost:3000/repo` rendered a GitHub-first workflow:

- Sidebar item: `Repo Import` with description `GitHub import and mission scoping`.
- Page eyebrow: `GitHub Import`.
- Page title: `Repository Intake and Mission Configuration`.
- Step 1 heading: `Step 1: Import Repository`.
- Primary field: `GitHub repository URL`, type `url`, placeholder `https://github.com/org/project`.
- Secondary field: `Branch`, default `main`.
- Browser-mode local hint: `Desktop app: Browse local repos`.
- Primary action: `Import Repository`.
- Step 2 empty state: `Import a repository to preview files...`.

Required page changes:

Status: complete for the current `/repo` route as of 2026-07-02, except for
extracted-folder/index-status UI that belongs to repo knowledge ingestion.

- Keep the page title if desired, but change the eyebrow to `Repository ZIP Import`.
- Change Step 1 heading to `Step 1: Import Repository ZIP`.
- Replace the URL row with a file-picker row:
  - browser mode: visible `.zip` file input/drop zone
  - Electron mode: `Browse ZIP...` button backed by the existing Electron open dialog
  - selected file summary: file name, size, and pending/validated state
- Change `Branch` to `Source ref` or `Commit/ref label`. The app should treat it as metadata only, not as a ref it resolves.
- Keep `Subdirectory` and `Max files`, but place them under `Import options` so the ZIP file remains the primary visual control.
- Change the primary action to `Index ZIP` or `Import ZIP`.
- Add a compact archive metadata summary after import:
  - archive file name
  - archive SHA-256 short prefix
  - inferred root prefix
  - selected subdirectory
  - skipped large/unsafe entries
- Update Step 2 empty state to `Import a ZIP archive to preview files...`.
- Keep the file overlay list, filter, include/reference/exclude controls, review gate, and launch step. Those map well to the archive-backed flow.
- Add a warning or risk note when unsafe entries are skipped or when a ZIP has multiple top-level roots.

Affected UI and client files:

- `apps/mission-control/app/(shell)/repo/page.tsx`: primary UI rewrite from URL state to file/archive state.
- `apps/mission-control/app/lib/navigation.ts`: sidebar description should become `Local ZIP import and mission scoping`.
- `apps/mission-control/app/lib/types.ts`: `RepoReviewResponse.repository` currently requires `owner`, `repo`, `branch`, and `html_url`; it needs ZIP-compatible fields such as `source`, `display_name`, `archive_id`, `archive_sha256`, `source_ref`, and nullable `html_url`.
- `apps/mission-control/app/lib/types/api.ts`: `RepoReviewRequest` is currently loose enough to accept new fields, but should be tightened once the ZIP contract is stable.
- `apps/mission-control/app/lib/api-client.ts`: `fetchJson` always sends `Content-Type: application/json`, so ZIP import should use a separate helper for `FormData` upload that does not force JSON headers.
- `apps/mission-control/app/lib/electron-bridge.ts`, `apps/mission-control/electron/preload.ts`, and `apps/mission-control/electron/main.ts`: keep the existing open-dialog bridge, but change the repo page usage from `openDirectory` to `openFile` with a ZIP filter.
- `apps/mission-control/app/(shell)/settings/page.tsx`: keep the GitHub PAT vault slot, but remove any implication that repository ZIP import depends on it. If remote GitHub import remains later, label it as optional remote source access.
- `apps/mission-control/app/(shell)/missions/detail/page.tsx`: mission metadata should display/archive source cleanly if repo missions are surfaced later. Use `source: repo-zip-import-ui`, `archive_sha256`, `source_ref`, and `display_name` instead of GitHub-only `repo_url`, `repository_owner`, and `repository_name`.
- `apps/mission-control/app/(shell)/missions/detail/panels/operational/GeneratedOutputPanel.tsx`: wording that says artifacts are not written into the repository checkout should remain true, but should not imply a local Git checkout exists. Prefer `source archive or checkout`.
- `apps/mission-control/e2e/mission-control.spec.ts`: repo intake mocks and assertions currently validate `repo_url` and GitHub text. Update them to multipart/upload semantics or isolate the ZIP route behind helper mocks.

UI validation checklist:

- Browser mode shows a usable ZIP input, not only a desktop hint.
- Electron mode opens a file picker filtered to `.zip`.
- Import cannot run without a selected ZIP.
- Changing ZIP file, source ref, subdirectory, max files, or overlay actions resets the review gate.
- Import logs never mention GitHub metadata, GitHub trees, rate limits, or private repository tokens.
- Review summary and source bundle headers identify the archive source and hash.
- Mission launch metadata remains compact enough for backend limits.
- E2E tests cover the ZIP import happy path and the invalid/missing archive state.

## Actual Code Reconciliation Update

After comparing this plan to the current code, the repository indexing path must be adjusted in four areas:

- Mission Control can read the uploaded ZIP and can extract it into a user-visible Windows folder, but the orchestrator and API gateway must not be assumed to have filesystem access to that folder. In the current local stack, PM/agent knowledge lives behind the orchestrator database APIs, so repository content has to be pushed to the orchestrator as bounded records over HTTP.
- `POST /v1/missions` in `services/api-gateway/api_gateway/main.py` persists the mission through orchestrator `/missions`, and orchestrator `routes/missions.py` immediately calls `start_lifecycle_task`. In Mission Flow v2, `MissionState.queued` runs `_prepare_pm_intake` before the FETCH/IS phase. Therefore, a ZIP repo launched through the existing `createMission()` call can race PM intake unless PM intake explicitly waits for repo indexing.
- The frontend has `updateMissionMetadata()` in `apps/mission-control/app/lib/api-client.ts`, but the API gateway currently does not expose a matching `PATCH /v1/missions/{mission_id}` route. The indexing completion path cannot depend on that client helper until a backend route is added.
- `mission_knowledge` already has a mission FK and `/internal/knowledge` only upserts one record at a time. Add a bulk repo-index endpoint rather than looping hundreds of UI-side calls through the single-record route.

Updated code-aligned launch and index flow:

1. `POST /api/repo/import` stores the archive in a Mission Control controlled staging cache, extracts a safe copy into the user-visible folder, and returns an `import_id` plus manifest.
2. `POST /api/repo/review` reads selected files from the staged import, not from GitHub.
3. Mission launch still calls `createMission()` with the selected approved `source_code`, but includes compact metadata:
   - `source: "repo-zip-import-ui"`
   - `repo_import.import_id`
   - `repo_import.archive_sha256`
   - `repo_import.index_required: true`
   - `repo_import.index_status: "pending"`
   - no raw file chunks in metadata
4. Add a guard at the top of `_prepare_pm_intake` in `services/orchestrator/orchestrator/mission_flow_v2/phases_intake.py`: if `metadata.repo_import.index_required` is true and `index_status` is not `complete`, persist a `REPO_INDEX_PENDING` chain/audit marker and return `False` while the mission remains queued.
5. Immediately after mission creation, the repo page calls a new Mission Control server route, for example `POST /api/repo/index`, with `mission_id` and `import_id`. That route reads the staged ZIP/extracted safe file list, builds bounded repo manifest/summary/chunks, and posts them to a new orchestrator internal endpoint with `INTERNAL_SERVICE_API_KEY`.
6. Add `POST /internal/missions/{mission_id}/repo-import-index` in the orchestrator. It should:
   - verify the mission exists
   - write repo knowledge rows to `mission_knowledge`
   - mirror to Qdrant/Milvus/Neo4j using the same best-effort behavior as `/internal/knowledge`
   - update `metadata.repo_import.index_status`, counts, errors, and `repo_knowledge_ids`
   - call `start_lifecycle_task(app, mission_id)` so the queued mission resumes PM intake after indexing completes
7. Add an optional API gateway proxy only if the browser UI cannot call the Mission Control server route. Prefer keeping the internal service key inside Next server routes, following the existing review approval route pattern.

This means the extracted folder is for operator inspection and later local workflows. The application's internal database remains the agent-facing source of truth.

## Extraction And Repository Indexing Design

The ZIP import should produce two durable outputs:

1. A user-visible extracted repository folder the operator can find and open.
2. Mission-scoped repository knowledge records in the application's internal database so the PM Agent and downstream agents can use the repo as context.

### User-visible extraction folder

Do not extract uploaded ZIP files into the source checkout, temporary directories, or hidden app internals as the primary operator-facing location. Use a stable local workspace root such as:

- Windows default: `%USERPROFILE%\Documents\HolyGrail\Repository Imports`
- Override: `MISSION_CONTROL_REPO_IMPORT_ROOT`

Each import gets its own sanitized subfolder:

`<repo-display-name>-<archive-sha256-12>`

Example:

`C:\Users\<user>\Documents\HolyGrail\Repository Imports\sample-platform-a1b2c3d4e5f6`

Extraction behavior:

- First inspect the ZIP entries without extracting.
- Reject or skip unsafe entries before writing anything: absolute paths, drive letters, UNC paths, `..`, null bytes, empty path segments, symlink-like entries, and files exceeding configured limits.
- Strip a common GitHub archive root such as `repo-branch/` or `repo-sha/` so the visible folder opens directly to the repo contents.
- Extract only safe file entries under the import subfolder, preserving directories.
- Write a small `.holygrail-import.json` manifest into the extracted folder with archive hash, import id, display name, source ref, root prefix, file counts, skipped entries, and indexed status.
- Keep the original uploaded ZIP either in an app-controlled cache or next to the extracted folder as `source.zip` only if the operator opts into retaining it.
- Add an `Open Folder` action on the repo page after import. In Electron, reuse `shellOpenArtifactDir`; in browser mode, show the absolute path as read-only text because a browser cannot open arbitrary local folders reliably.

The extracted folder is for operator inspection and future edit workflows. It should not be the source of truth for retrieval. The internal database index is the source of truth for PM/agent context.

### Import manifest contract

The import route should return and persist an import manifest:

```json
{
  "source": "repo_zip",
  "import_id": "repozip-a1b2c3d4e5f6",
  "display_name": "sample-platform",
  "archive_sha256": "a1b2...",
  "source_ref": "main-or-commit-label",
  "extracted_path": "C:\\Users\\kevin\\Documents\\HolyGrail\\Repository Imports\\sample-platform-a1b2c3d4e5f6",
  "root_prefix": "sample-platform-main/",
  "file_count": 314,
  "indexed_file_count": 0,
  "index_status": "pending"
}
```

This manifest should be included in mission launch metadata as `repo_import`, not expanded into large metadata fields.

### Repository indexer

Keep ZIP parsing, extraction, and chunk preparation in Mission Control's Node runtime because that is the process that receives the upload and owns the staged local archive. Do not make the orchestrator read `extracted_path`; in Docker/local-service layouts that Windows path may not exist inside the orchestrator container.

Add a repo-index ingestion endpoint in the orchestrator that accepts already prepared manifest, summary, and text chunks:

- `POST /internal/missions/{mission_id}/repo-import-index`
- payload: `import_manifest`, `summary_record`, `chunk_records`, `index_status`, `index_errors`
- auth: existing internal service key dependency
- behavior: validate mission, write records, mirror vectors, update mission metadata, and resume lifecycle

Recommended helpers:

- Mission Control: `buildRepoImportKnowledge(importId, missionId, options)` reads from the staged ZIP/extracted safe manifest and emits bounded knowledge records.
- Orchestrator: `upsert_repo_import_index(app, mission_id, payload)` writes rows through the same storage/vector mirror path as `/internal/knowledge`.
- PM intake: `load_repo_context(settings, mission_id, repo_import)` reads existing repo records and injects a bounded repository context block.

Indexing sequence in actual code:

1. Mission is created with `repo_import.index_required=true` and `index_status="pending"`.
2. `_prepare_pm_intake` checks that flag before calling `generate_pm_feature_contract`. If the repo index is not complete, it records `REPO_INDEX_PENDING` and returns `False`.
3. The Mission Control `/api/repo/index` route posts prepared repo records to `/internal/missions/{mission_id}/repo-import-index`.
4. The orchestrator endpoint writes `mission_knowledge`, updates `metadata.repo_import.index_status="complete"`, and calls `start_lifecycle_task(app, mission_id)`.
5. On the resumed queued lifecycle, `_prepare_pm_intake` loads repo records, adds `conversation_context["repository_context"]`, and only then calls `generate_pm_feature_contract`.

This keeps PM intake deterministic without adding raw repository chunks to mission metadata or relying on local path sharing between services.

### Knowledge record shape

Use the existing `mission_knowledge` table as the internal database source of truth. PostgreSQL writes are authoritative; Qdrant/Milvus/Neo4j mirrors remain best effort through the existing `/internal/knowledge` route.

Manifest record:

`knowledge_id = repo.<import_id>.manifest`

Content:

```json
{
  "kind": "repo_manifest",
  "source": "repo_zip_import",
  "import_id": "repozip-a1b2c3d4e5f6",
  "display_name": "sample-platform",
  "archive_sha256": "a1b2...",
  "extracted_path": "C:/Users/kevin/Documents/HolyGrail/Repository Imports/sample-platform-a1b2c3d4e5f6",
  "combined_text": "Repository sample-platform imported from ZIP. 314 files indexed...",
  "metadata": { "file_count": 314, "source_ref": "main" }
}
```

File/chunk records:

`knowledge_id = repo.<import_id>.file.<path-hash>.chunk.<n>`

Content:

```json
{
  "kind": "repo_source_chunk",
  "source": "repo_zip_import",
  "import_id": "repozip-a1b2c3d4e5f6",
  "path": "apps/web/page.tsx",
  "language": "TypeScript",
  "chunk_index": 0,
  "chunk_count": 3,
  "sha256": "file-or-chunk-sha",
  "combined_text": "...chunk text...",
  "content": "...chunk text...",
  "metadata": {
    "bytes": 12000,
    "estimated_lines": 260,
    "archive_sha256": "a1b2...",
    "selected_for_review": true
  }
}
```

Summary record:

`knowledge_id = repo.<import_id>.summary`

Content should include detected languages, package/config files, top directories, selected files, likely frameworks, and operator mission description. PM intake should read this record first because it is compact enough for prompt inclusion.

### PM Agent access

Current PM intake already builds `conversation_context` and resolves attachment content before calling `generate_pm_feature_contract`. Extend it to include repository context:

- Query `/internal/missions/{mission_id}/knowledge` or storage directly for records where `content.kind` starts with `repo_`.
- Build a bounded text block from `repo_manifest`, `repo_summary`, and the most relevant `repo_source_chunk` rows.
- Put that block into `conversation_context["repository_context"]`.
- Also add `repo_import` metadata fields so PM output can cite the source archive and extracted folder.

Downstream pod workers already fetch mission knowledge before extraction through `_fetch_doc_context`, but today that function only accepts `bootstrap_documentation`. Update it to also include bounded `repo_summary` and relevant `repo_source_chunk` records so specialist agents get repo context during extraction/build.

### Relationship to source bundles

Keep the existing source bundle path for selected files and build artifacts. The source bundle is the focused mission payload. The repository index is the broader retrieval layer.

- `source_code`: selected files approved by the operator, bounded by current source bundle limits.
- `repo_import`: manifest and extracted folder reference.
- `mission_knowledge`: searchable repo index and summaries for PM/agents.
- `source_bundle_package`: existing verified artifact at mission verification time.

This avoids putting the entire repository into `metadata.source_code`, which is capped and would make mission records too large.

### Indexing limits and safety

- Skip generated/vendor folders by default: `node_modules`, `.git`, `.next`, `dist`, `build`, `coverage`, `__pycache__`, `.venv`, binary/media folders.
- Always index manifest files and high-signal files first: `README*`, package manifests, lockfiles, config files, routing files, app entrypoints, tests.
- Chunk large text files by line-aware or token-aware bounds.
- Cap indexed files and chunks per import; expose truncation in UI and metadata.
- Store raw file text only in chunks that pass binary/text checks and size limits.
- Run PII/prompt-risk scanning on indexed text summaries where practical; record counts, not matched secrets.

### UI additions for indexing

After ZIP import, the repo page should show:

- Extracted folder path with `Open Folder` in Electron.
- Index status: `Not indexed`, `Indexing`, `Indexed`, or `Indexed with warnings`.
- File counts: extracted, skipped unsafe, skipped large, indexed chunks.
- `Re-index` action if the folder still exists and archive hash matches the manifest.
- A short note that PM Agent context is available only after indexing completes.

## Testing Plan

Unit tests:

- `parseGithubRepoUrl` tests should be replaced or moved behind a deprecated GitHub helper if kept.
- Add ZIP helper tests for:
  - common root prefix stripping
  - root-level ZIP support
  - subdirectory filtering
  - sorting and truncation
  - large file skip count
  - unsafe entry skip/reject cases
  - binary file metadata-only handling
  - archive SHA-256 consistency

Route tests:

- `repo/import/route.test.ts`
  - accepts multipart ZIP with operator session
  - rejects missing archive
  - rejects non-ZIP input
  - returns indexed files without calling `fetch`
  - reports unsafe entries without extracting them
- `repo/review/route.test.ts`
  - builds a review artifact from selected ZIP entries
  - rejects unknown or expired `archive_id`
  - rejects archive hash mismatch
  - preserves include/reference behavior and bundle limits

Frontend tests:

- Add or update component/Vitest coverage for file selection state and review reset behavior.
- Add Playwright/Electron smoke coverage for selecting a ZIP file if test fixture support exists.

Validation commands:

- `npm --prefix apps/mission-control run lint`
- `npm --prefix apps/mission-control run typecheck`
- `npm --prefix apps/mission-control run test`
- Existing repo-wide Python tests are not required for this frontend/API route change unless shared runtime docs or mission creation contracts are modified.

## Migration Phases

### Phase 1: Archive Core

Status: complete.

- Add ZIP helper module and fixture ZIPs.
- Implement safe archive indexing and selected file reading.
- Add focused ZIP helper tests.

### Phase 2: Import Route

Status: complete.

- Convert `POST /api/repo/import` to multipart ZIP import.
- Keep the response shape close to today, with ZIP metadata replacing GitHub metadata.
- Remove GitHub metadata/tree calls from this path.

### Phase 3: Review Route

Status: complete for re-uploaded multipart review; staged archive review remains
part of the future repo-indexing work.

- Convert `POST /api/repo/review` to read selected file contents from staged ZIP archives.
- Preserve review artifact output and fingerprinting semantics.
- Include archive hash and source ref in fingerprinting.

### Phase 4: UI Migration

Status: complete for browser-compatible ZIP selection, FormData import/review,
archive metadata, and review-gate reset behavior. Extracted-folder and
index-status UI remain tied to phases 5-7.

- Replace URL input with ZIP chooser.
- Update copy, validation, metadata, and review reset behavior.
- Remove misleading local-directory browse path.
- Add extracted-folder and index-status UI, including Electron `Open Folder` support.

### Phase 5: Mission Launch Guard

- Launch repo ZIP missions with compact `metadata.repo_import` and `index_status="pending"`.
- Add the `_prepare_pm_intake` guard so PM contract generation waits for completed repo indexing.
- Add tests proving queued repo missions do not proceed to PM intake while index status is pending.

### Phase 6: Repo Knowledge Ingestion

- Add Mission Control `POST /api/repo/index` to read the staged import and build bounded knowledge records.
- Add orchestrator `POST /internal/missions/{mission_id}/repo-import-index` for manifest/summary/chunk ingestion.
- Reuse or factor the existing `/internal/knowledge` mirror logic so PostgreSQL remains authoritative and vector/graph mirrors stay best effort.
- Resume the queued lifecycle after successful index persistence.

### Phase 7: Agent Context Wiring

- Extend PM intake to load repo manifest/summary/chunks from mission knowledge and inject bounded `conversation_context.repository_context`.
- Extend pod worker knowledge context to include bounded `repo_summary` and relevant `repo_source_chunk` records, not only `bootstrap_documentation`.
- Add tests for PM context inclusion and pod-worker retrieval filtering.

### Phase 8: Cleanup and Documentation

- Update navigation, operator docs, and any README references to GitHub import. Status: complete for the current ZIP UI closeout.
- Decide whether to delete GitHub helper functions or keep them isolated for future remote-import support.
- Document ZIP snapshot limitations: no history, no submodule hydration, no LFS hydration.

## Risks and Decisions

- Archive staging storage: choose local app data/cache instead of the repo tree to avoid accidentally committing uploaded source archives.
- ZIP bombs: enforce entry count and total uncompressed byte limits before reading selected content.
- Reproducibility: encourage operators to upload commit-SHA source archives or release assets when they need stable inputs.
- Browser support: browser upload works, but large archives may hit Next.js/server body limits; Electron local file path handoff may be preferable for desktop.
- GitHub replacement scope: this plan removes remote GitHub import from the primary path. A future "Remote GitHub ZIP URL" feature can be added later, but it should still normalize into the same archive pipeline.

## Recommended Next Implementation Slice

Phases 1-4 are implemented and locally validated. The next slice should add the
mission launch index guard, repo knowledge ingestion, and PM/pod-worker
repository context loading before treating ZIP-imported repositories as
agent-accessible internal database context.
