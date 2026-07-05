# Full-Application Code Review — Findings (2026-07-05)

Document version: 2026.07.05
Last updated: 2026-07-05
Status: Active findings report — **review only, nothing in this document has been fixed yet**
Audience: Maintainers and AI coding agents planning the next remediation pass

This is a read-only, whole-application code review covering every part of
theFactory: the Mission Control frontend UI, the Electron/Windows packaging
layer, the dedicated agent-runtime service, deploy/infrastructure/CI
configuration, and the `scripts/` directory. It supplements (does not
replace) the backend slice-by-slice reviews already completed earlier this
project (Mission Flow v2, storage layer, orchestration core, api-gateway,
pod-worker, verification/compliance gates, `shared_runtime`) and the Mission
Control **API routes** review, both of which already had their bugs fixed and
committed.

**No code, configuration, or documentation was changed while producing this
report.** Every finding below is unfixed as of this writing. The purpose of
this document is to give a complete, evidence-backed picture of the
application's current state so that a single, ordered upgrade/remediation
plan can be written next, as a separate step.

---

## 0. How this review was conducted

Five review passes, each read-only:

| Slice | Scope | Method |
|---|---|---|
| A | Mission Control frontend UI (`apps/mission-control/app/**`, excluding `app/api`) | Dedicated background review agent |
| B | Electron/Windows packaging (`apps/mission-control/electron/**`, `package.json` build config, `.github/workflows/release.yml`) | Dedicated background review agent (this slice was scoped and researched first, against Electron's official security checklist and Windows code-signing/NSIS best practices) |
| C | `services/agent-runtime/` (dedicated agent runtime process) | Direct self-review (only 3 files) |
| D | `deploy/`, `.env.example`, CI workflows, alerting/metrics docs | Dedicated background review agent |
| E | `scripts/` (58 scripts) and the `Makefile` | Dedicated background review agent |

All findings carry a confidence/severity assessment from the reviewing agent
and file:line evidence. Where an agent's read of the code was independently
re-confirmed by a second pass, that is noted.

---

## 1. Current runtime reality — read this first

**The application does not currently run as a packaged Electron desktop app.
It runs as a web app.** Concretely:

- `start_app.bat` (repo root) does two things: **`[1/2]`** starts the Docker
  Compose backend (`make up` / `make up-condensed`, or a Windows fallback that
  runs `docker compose --env-file .env -f deploy\docker-compose.yaml -f
  deploy\docker-compose.full-dedicated-agents.yaml --profile
  full-dedicated-agents up -d --build` with an explicit full service list of
  all 18 core services plus all agent containers); **`[2/2]`** reads
  `INTERNAL_SERVICE_API_KEY`/`MISSION_API_BASE_URL` from `.env`, `cd`s into
  `apps\mission-control`, and spawns a **new terminal window** running a
  plain Next.js standalone server (`npm run build && npm run start` on port
  3000, or `npx next dev -p 3000` in `--dev` mode) — then polls
  `http://localhost:3000` and opens it with `Start-Process $url`, i.e. the
  user's **default web browser**, not an Electron window.
- `stop_app.bat` calls `scripts\force_stop.py`, which tears down the same
  Docker Compose stack (falling back to `... down -v`, which deletes the
  `postgres-data`/`redis-data` volumes — a previously-documented gotcha, see
  memory `project_stack_ops_gotchas_2026-07-01.md`).
- The **Electron app is a separate, parallel build path** that exists in the
  repo (`apps/mission-control/electron/`, `electron:build`/`electron:package`
  npm scripts, `.github/workflows/release.yml`) but is not what
  `start_app.bat` launches, and — per §4/§8 below — cannot function correctly
  as packaged today because of a build-mode incompatibility with the app's
  API routes.

Any reader of this document should treat "the app" as **the web-app path
(Docker + browser tab)** unless a finding explicitly says "Electron" or
"packaged app."

---

## 2. Executive summary of findings

| # | Slice | Finding | Severity |
|---|---|---|---|
| 1 | Deploy | `RQCA_ENFORCEMENT_ENABLED` compose default (`false`) silently reverts the hardened code-level default (`true`) in every profile, including prod | High |
| 2 | Deploy | Production overlay never overrides MinIO credentials — falls back to `minioadmin`/`minioadmin123` | High |
| 3 | Frontend | Alert "Acknowledge"/"Mark Resolved" actions never call an API — local-state only, reverts on refresh | High |
| 4 | Electron | `app/api/*` (14 route files) cannot function in the packaged app — static export physically hides them at build time | High (architectural) |
| 5 | Electron | Release artifacts are unsigned; no `CSC_LINK`/cert wired anywhere in the repo | High |
| 6 | Scripts | Real (`--dry-run` off) DR drill mode runs destructive `docker compose down -v` by default | High |
| 7 | Scripts | Qualification scripts mutate live containers/auth config with no dry-run or confirmation gate | High |
| 8 | Scripts | Git-history-scrub script unconditionally rewrites history with no dry-run/backup | High |
| 9 | Scripts | `OPERATIONS_RUNBOOK.md`'s own recovery steps violate its own compose-pairing warning | High |
| 10 | Scripts | Duplicate `demo:` Makefile target silently shadows the intended one | High |
| 11 | Frontend | Mission/detail/artifact data fetches have no stale-response guard — wrong mission's data can render under a new mission's header | High |
| 12 | Frontend | Non-semantic clickable `<div>`s (copy-path card, protocol-bus rows) — mouse-only, no keyboard access | High |
| 13 | Frontend | Guided-tour dialog never calls `.focus()` — unreachable via keyboard alone | Medium-High |
| 14 | Frontend | Literal `✕` renders as 6 raw characters instead of "✕" in mission detail | High (cosmetic) |
| 15 | Deploy | `METRICS_SOURCE_MODULES.md` (rewritten this session) omits 4 real in-use metrics | High (doc accuracy) |
| 16 | Electron | Docker-availability check is cosmetic — non-blocking dialog, window loads regardless | Medium-High |
| 17 | Electron | No NSIS install/uninstall hooks anywhere; uninstall never removes containers/images/volumes/vault | Medium-High |
| 18 | Deploy | `GATEWAY_ADMIN_BYPASS=true` only warns in prod instead of failing fast like the adjacent CORS check | Medium-High |
| 19 | Scripts | `restore_postgres.ps1` — destructive restore over live DB, no confirmation/snapshot/checksum | Medium-High |
| 20 | Scripts | `force_stop.py` always tears down full pairing even in `--condensed` mode | Medium-High |
| 21 | Frontend | Chat sessions (up to 30, full message text) persist unencrypted in `localStorage` indefinitely | Medium |
| 22 | Frontend | No consistent 401/403 handling; `app/unlock/page.tsx` is an effectively dead stub | Medium |
| 23 | Deploy | `CORS_ALLOW_ORIGINS` hardcoded to `localhost:3100`, never overridden for prod | Medium |
| 24 | Deploy/Scripts | `--condensed` dev profile uses the base compose file alone, including volume-destroying `down -v` — intentional but unguarded against drift | Medium |
| 25 | Scripts | Weak well-known default secrets (`operator-key`, `dev-oidc-shared-secret`) forgeable if env unset | Medium |
| 26 | Agent-Runtime | `SERVICE_API_KEY` defaults to well-known `"worker-key"` if env unset | Medium |
| 27 | Scripts | `normalize_document_headers.py` bulk in-place rewrite, no backup/dry-run, non-atomic | Medium (mechanism), low (current impact) |
| 28 | Deploy | Stale casing mismatch: docs/comment say lowercase mission states, code/alerts correctly use uppercase | Low (doc-only) |
| 29 | Scripts | Several scripts (`generate_postgres_tls_certs.py`, `rotate_secrets.sh`, `dr_drill.ps1`, `run_demo_mission.py`, cert generators) — no `--force` guard, non-atomic writes, hardcoded `passed=true`, placeholder fallback key | Low-Medium |
| 30 | Frontend | No `dangerouslySetInnerHTML` anywhere; no XSS vector found | None (clean) |
| 31 | Frontend | Repo/builder import approval fingerprints are server-verified; client checks are UX-only | None (clean, no bypass) |
| 32 | Scripts/Deploy | Dockerfile hygiene, CI security workflow coverage (`pip-audit`/`bandit`/`Trivy`/`gitleaks`) | None (clean) |
| 33 | Agent-Runtime | Circuit breaker, retry/backoff, audit-event emission, consumer-loop ack semantics | None (clean) |

Findings are grouped and detailed by slice below. Numbering restarts per
slice for readability; the table above is the cross-slice severity index.

---

## 3. Slice A — Mission Control Frontend UI

Scope: `apps/mission-control/app/**` excluding `app/api/*` (covered under
Electron/packaging in §4, since those routes' relevance is really about the
Electron build).

1. **(High)** `app/(shell)/missions/output/hooks/useArtifactData.ts:31-54` —
   no stale-response guard or request cancellation. Navigating between
   missions while a fetch is in flight can render the previous mission's
   artifact/code content under the new mission's header.
2. **(High)** `app/(shell)/missions/detail/page.tsx:127-160` — same
   missing-cancellation defect, compounded by SSE plus a polling fallback
   both able to trigger `loadDetails` independently (three call sites).
3. **(Medium)** `app/(shell)/missions/page.tsx:158-184,230-238,254-271` — race
   between synchronous selection state and async detail load; the polling
   loop's `cancelled` flag only stops the *next* tick, not an in-flight
   request.
4. **(High)** `app/(shell)/alerts/page.tsx:81-92,168-172` — "Acknowledge" and
   "Mark Resolved" only mutate local React state. No API call persists
   either action; a refresh reverts it. Operators can be misled into
   believing an alert was actioned when it was not.
5. **(Medium-High)** `app/components/guided-tour.tsx:213-221` — the tour
   dialog wires keyboard handlers but never calls `.focus()` on open (unlike
   sibling components `KeyboardShortcuts` and `DialogProvider`, which do),
   making it unreachable by keyboard-only navigation.
6. **(High)** Non-semantic clickable `<div>`s: the copy-path card in
   `app/(shell)/missions/output/page.tsx:125-156` and table rows in
   `app/(shell)/protocol-bus/page.tsx:463` are mouse-only — no `role`,
   `tabIndex`, or `onKeyDown` — contrasted with the correct pattern already
   used in `FileTreePane.tsx:59-94`.
7. **(High, cosmetic)** `app/(shell)/missions/detail/page.tsx:455` — a literal
   `✕` appears as bare JSX text (not inside a quoted string), so it
   renders as the 6 raw characters `✕` instead of the intended "✕"
   glyph. Lines 493 and 603 in the same file do this correctly (quoted).
8. **(Medium)** `app/(shell)/chat/page.tsx:82-84,652-680` — up to 30 chat
   sessions, including full prompt/message text, persist unencrypted in
   `localStorage` indefinitely. Lower severity given the local-only Electron
   threat model, but still worth deciding on retention/encryption policy.
9. Settings/vault page correctly avoids plaintext secret exposure — no issue
   found.
10. **(Clean)** No `dangerouslySetInnerHTML` anywhere in scope; all
    LLM-generated content is rendered through auto-escaping JSX or
    `react-syntax-highlighter` — no XSS vector found.
11. **(Medium)** No consistent client-side 401/403 handling. Only one
    fragile string-matching heuristic exists
    (`chat/page.tsx:203-220`, `isOperatorAuthError()`), not applied on other
    pages. `app/unlock/page.tsx` unconditionally redirects to `/settings` and
    is effectively a dead stub.
12. Root/shell `error.tsx` boundaries plus per-panel `ErrorBoundary` wrapping
    (22 panels in mission-detail) are adequate — no gap beyond #11.
13. **(High confidence, no bypass risk)** Repo/builder import flows have
    server-side-verified approval fingerprints; client-side validation is
    UX-only and cannot be used to bypass approval.

**Reviewed with no material findings:** `tooltip.tsx`, `command-palette.tsx`,
`keyboard-shortcuts.tsx`, `dialog-provider.tsx` (correct ARIA/focus
management); `electron-bridge.ts` (clean, narrowly-typed IPC surface);
`security.ts`, `format.ts`, `language.ts`, `mock-data.ts`. `global-search.tsx`
appears to be dead code, superseded by `command-palette.tsx` — worth
confirming and removing in a future cleanup pass (not fixed here, per the
review-only scope).

---

## 4. Slice B — Electron / Windows Packaging

Scope: `apps/mission-control/electron/**`, `package.json` build/NSIS config,
`.github/workflows/release.yml`, plus the Next.js dual-build-mode split that
underlies all of it.

1. **(High)** `electron/main.ts:19-29` — `checkDockerAvailability()` only
   runs `execSync("docker version", { stdio: "ignore" })`, i.e. it checks
   that the Docker CLI/engine is reachable, **not** that the actual 18+
   container application stack is running.
2. **(High)** `electron/main.ts:115-131` — `app.whenReady()` calls that check
   and shows a non-blocking `dialog.showErrorBox` on failure, but falls
   through unconditionally to `createWindow()` on the very next line
   regardless of the check's result or the dialog's dismissal. The check is
   cosmetic: a missing or unhealthy backend does not stop the Electron window
   from opening a UI that will then fail to fetch any data.
3. **(High, architectural)** Confirmed core build-mode blocker:
   `next.config.mjs:1-23` sets `nextConfig.output = "export"` for any build
   where `NEXT_BUILD_TARGET !== "docker"` (which includes the Electron
   build's `"electron"` target). Next.js static export is fundamentally
   incompatible with dynamic App Router API routes
   (`export const runtime = "nodejs"`, present in all 14 files under
   `app/api/**/route.ts` — vault, vault/test, session/unlock, session/logout,
   review/approve, review/verify, builder/review, repo/import, repo/review,
   operator/mission-state, pm/feature-contract, local/open-vscode,
   local/open-output-folder, local/output-folder-status, gateway/[...path]).
   `apps/mission-control/scripts/build-electron.mjs:32-50` physically renames
   `app/api` → `app/_api_hidden` before running `next build`, with an
   explicit comment ("Hiding API directory to prevent static export errors"),
   then renames it back afterward — direct proof the authors already know
   these two build modes cannot coexist. **Practical consequence: none of
   the 14 API routes function in the packaged Electron app today** — vault
   unlock, session management, mission review/approval, repo import, and the
   gateway proxy are all absent from the shipped build.
4. **(Medium-High)** `apps/mission-control/app/lib/server/vault.ts:~91-92` —
   vault path resolves to `process.env.VAULT_DATA_PATH?.trim() ||
   join(homedir(), ".thefactory", "vault.json")`, i.e. `~/.thefactory/vault.json`
   — outside Electron's `userData` directory. `deleteAppDataOnUninstall:
   true` in the NSIS config (`package.json`) does **not** actually delete
   this file, contrary to what the setting name implies.
5. **(Medium-High)** `package.json` `build.nsis` config
   (`oneClick: false`, `allowToChangeInstallationDirectory: true`,
   `deleteAppDataOnUninstall: true`, `runAfterFinish: true`) has **no
   dependency checks** (Docker Desktop / WSL2 presence), and **no custom
   install/uninstall scripts** — confirmed no `apps/mission-control/build/`
   directory and no separate `electron-builder.yml`/`.json`/`.js` config
   exists anywhere in the repo.
6. **(High)** No Docker/Compose lifecycle code exists anywhere in the
   Electron main process. Grep for `docker|compose|spawn|exec`
   (case-insensitive) across all of `electron/` returns exactly the one
   `execSync("docker version")` call from finding #1 — nothing starts,
   stops, or supervises the backend containers from the Electron app itself.
   `electron/main.ts:202-206`'s `window-all-closed` handler only calls
   `app.quit()` on non-macOS; there is no teardown call.
7. **(High)** `package.json`'s `build.win.signtoolOptions.publisherName:
   "Kevin Herrera"` is set, but there is **no `certificateFile`/`CSC_LINK`
   anywhere** in the repo. This label alone does not sign anything —
   electron-builder silently skips signing when no certificate is supplied.
   `.github/workflows/release.yml:~58-63` runs `npm run electron:package`
   with only `GITHUB_TOKEN` set, and contains the comment `# Future: CSC_LINK
   and CSC_KEY_PASSWORD for code signing`. Grep for
   `CSC_LINK|signtoolOptions|certificateFile|codesign|CSC_KEY_PASSWORD`
   across the repo only hits this unused label, this comment, and
   forward-looking prose in `OPERATIONS_RUNBOOK.md`. **Release artifacts are
   confirmed unsigned.** Per current Microsoft SmartScreen policy (post-June
   2023), even a standard (non-EV) certificate no longer suppresses the
   "Unknown Publisher" warning on first run — only an EV cert or built-up
   reputation does, which is a cost/process decision, not just a config
   change.
8. `electron/preload.ts` (66 lines) — clean, narrow
   `contextBridge.exposeInMainWorld("electronAPI", {...})` surface (window
   controls, tray update, file dialogs, app version, `openArtifactDir` via
   `shell.openPath`, `getPlatform`, diagnostics). No raw `ipcRenderer`
   passthrough — correct per the Electron security checklist.
9. `electron/updater.ts` (14 lines) — auto-update is **intentionally
   disabled** (module docstring: "Auto-update has been intentionally
   disabled. Updates are handled manually via the Windows installer
   (NSIS)."). Only `app.getVersion()` is exposed. This is a deliberate design
   decision, not a gap — noted here so it isn't mistaken for one in the
   upgrade plan.
10. `createWindow()` correctly sets `contextIsolation: true`, `nodeIntegration:
    false`, `sandbox: true`; `setWindowOpenHandler`/`will-navigate` correctly
    restrict navigation to `http://localhost`/`file://`, routing everything
    else through `shell.openExternal` — both per the Electron security
    checklist.
11. CSP is set via a `<meta httpEquiv="Content-Security-Policy">` tag in
    `app/layout.tsx:30-44` (necessary because `next.config` `headers()` are
    ignored under `output: export`). It includes `script-src 'self'
    'unsafe-inline'`, which weakens the CSP's protection against injected
    inline scripts. Worth a closer look in the remediation pass — not
    independently re-confirmed by the whole-app pass beyond the original
    Electron-focused review.
12. `ci.yml:507` references `secrets.RELEASE_TAG_GPG_PUBLIC_KEY` to verify
    signed release tags — an actively-used, fail-the-job-if-empty step. Its
    actual GitHub secret configuration cannot be verified from a local
    checkout and should be confirmed operationally.

---

## 5. Slice C — Agent Runtime (`services/agent-runtime/`)

Scope: `main.py` (769 lines), `tracing.py` (54 lines), `__init__.py`
(3 lines) — the dedicated per-agent worker process used by the
41-agent full-dedicated topology.

Overall this service is in good shape: a real circuit breaker with
half-open recovery probing (`_CircuitBreaker`, lines 103-153), bounded
retry/backoff on orchestrator calls (`_request`, lines 232-301), consistent
audit-event emission around execution start/complete
(`_emit_audit_event`/`_process_event`), a Redis consumer-group loop with
correct ack semantics (invalid/malformed events are acked and discarded
rather than retried forever; transient failures are not acked and will
redeliver), and a heartbeat loop independent of the consumer loop. Tracing
setup (`tracing.py`) fails safe (`try`/`except` around all OTEL imports and
instrumentation calls, defaults to disabled rather than crashing the
service).

1. **(Medium)** `main.py:53` — `SERVICE_API_KEY = os.getenv("SERVICE_API_KEY",
   "worker-key")` falls back to the well-known literal `"worker-key"` if the
   environment variable is unset. This is the same weak-default-secret
   pattern already flagged independently in Slice E (`operator-key`,
   `dev-oidc-shared-secret` — see §6 finding 9): if an operator forgets to
   set `SERVICE_API_KEY` in a given environment, the agent-runtime
   authenticates to the orchestrator with a publicly-known value.
2. No other material findings. The generic `except Exception` catches in
   `_consumer_loop` (line 663) and `_heartbeat_loop` (line 686) are
   appropriately scoped — they log and continue rather than silently
   swallowing errors that should surface, and are consistent with this
   service's fail-forward design (a single bad event or heartbeat failure
   should not kill the process).

---

## 6. Slice D — Deploy / Infrastructure / CI

Scope: `deploy/docker-compose*.yaml`, `.env.example`, service settings that
interact with compose-level env vars, Prometheus alert rules, metrics
documentation, Dockerfiles, and GitHub Actions workflows.

1. **(High)** `deploy/docker-compose.yaml:326` sets
   `RQCA_ENFORCEMENT_ENABLED: ${RQCA_ENFORCEMENT_ENABLED:-false}`. This
   silently reverts the code-level hardened default (`true`, per
   `services/orchestrator/orchestrator/settings.py:373-375`, changed earlier
   this session) back to `false` in **every** compose profile, including
   production — confirmed via `docker compose config` merge output against
   `docker-compose.prod.yaml`, which never overrides this variable.
   `.env.example:182` also documents the insecure `false` value. Unlike other
   hardened settings, there is no `is_production` runtime guard that would
   catch this at app startup.
2. **(High)** The production overlay never sets MinIO/object-storage
   credentials. `deploy/docker-compose.yaml:222,289-290` fall back to the
   well-known defaults `minioadmin`/`minioadmin123`; `docker-compose.prod.yaml`
   has zero references to these variables, and no app-level fail-fast check
   exists to catch a production deployment still running on default
   credentials.
3. **(Medium)** `CORS_ALLOW_ORIGINS` is hardcoded to `http://localhost:3100`
   in the base compose file and is never overridden in the prod overlay
   (confirmed via `docker compose config` merge). This is not a
   wildcard-CORS vulnerability — `api_gateway/main.py:1660-1661` already
   fails fast on a literal `*` in production — but it is an operational
   correctness risk: legitimate production domains would be rejected, or a
   stale `localhost` trust entry would be left in a production config.
4. **(Medium)** `start_app.bat --condensed` / `make up-condensed` /
   `down-condensed` use the base compose file alone, including a
   volume-destroying `down -v`. This is assessed as an intentional,
   currently self-sufficient dev profile (the condensed topology's services
   are all defined in the base file), but it is structurally unguarded
   against future drift — the same shape as the already-known
   compose-pairing incident pattern documented in memory.
5. **(Medium-High)** `services/api-gateway/api_gateway/main.py:1663-1667` —
   `GATEWAY_ADMIN_BYPASS=true` in production only logs a warning, whereas the
   adjacent CORS-wildcard check three lines above it (`1660-1661`) raises a
   `RuntimeError` and fails fast. Inconsistent enforcement posture between
   two settings of comparable severity. (Compose files themselves correctly
   default `GATEWAY_ADMIN_BYPASS` to `false`.)
6. **(High, doc accuracy)** `docs/METRICS_SOURCE_MODULES.md` — rewritten
   earlier this session as part of the documentation audit and presented as
   a complete/verified inventory — omits four real metrics that are actually
   used by alert rules and dashboards: `pod_worker_task_latency_seconds`,
   `agent_runtime_task_latency_seconds`, `audit_worker_task_latency_seconds`
   (all confirmed to exist in their respective services' `main.py`), and
   `factory_llm_tokens_total` (confirmed in `llm_delegation/metrics.py:39-40`).
   This is a documentation-completeness gap, not a functional alerting bug —
   the alert/dashboard expressions themselves are valid against real
   metrics.
7. **(Low, doc-only)** Stale casing mismatch: `orchestrator_metrics.py:57`'s
   comment and `docs/METRICS_SOURCE_MODULES.md:19` both describe mission
   states in lowercase (`queued | running | verified`), but the actual
   `_ACTIVE_GAUGE_STATES` set (`orchestrator_metrics.py:79`) and the real
   `MissionStuckInRunning` alert query both correctly use uppercase
   (`QUEUED`/`RUNNING`/`VERIFIED`). Comment/doc staleness only — not a
   functional bug.
8. **(Clean)** Dockerfile hygiene — all Dockerfiles are digest-pinned,
   multi-stage, run as non-root, and `.dockerignore` correctly excludes
   `.env*`, `.git`, `*.pem`/`*.key`/`*.crt`, and `secrets/`.
9. **(Clean)** CI/CD security workflow coverage — `security.yml` genuinely
   runs pip-audit, bandit, Trivy, gitleaks, and license scans (not
   aspirational documentation); no script-injection vectors found in any
   workflow. `release.yml` has no code-signing wired up, consistent with the
   Electron slice's finding above.
10. `qualification.yml` and the DR-drill script's use of the base compose
    file alone for the `dedicated-agents` profile (not
    `full-dedicated-agents`) is correct and self-sufficient — the 4
    dedicated-manager-worker services for that profile are defined directly
    in the base file. Not a violation of the compose-pairing convention.

---

## 7. Slice E — `scripts/` directory and `Makefile`

Scope: all 58 scripts under `scripts/`, plus `Makefile`.

1. **(High)** `docs/OPERATIONS_RUNBOOK.md:223-230` — the runbook's own
   "Recovery Steps" section violates its own compose-file-pairing warning,
   instructing operators to run the base compose file alone during exactly
   the restart scenario that warning exists to prevent.
2. **(High)** `Makefile:88-90` vs. `195-196` — a duplicate `demo:` target
   exists; the second definition silently shadows the first, so `make demo`
   never runs the intended `demo_missions.py --dry-run` evidence generator.
3. **(High)** `scripts/run_automated_dr_drill.py:96` — "real recovery drill"
   mode runs `docker compose down -v` with `--dry-run` as an opt-in flag
   rather than the default. A single missing flag causes real data loss.
4. **(High)** `scripts/operator_route_auth_matrix_qualification.py` and
   `scripts/langgraph_postgres_recovery_qualification.py` default to live,
   destructive container mutation (force-recreating/rebuilding the live
   api-gateway/orchestrator containers, flipping auth modes) with no
   dry-run or confirmation gate — a more severe variant of the already-known
   `force_stop.py` issue, since it also mutates live auth configuration.
5. **(High)** `scripts/execute_git_history_scrub.ps1` / `.py` —
   unconditionally rewrites git history
   (`git filter-repo --invert-paths --force`) with no dry-run,
   confirmation, or backup tag. The comment-based guard only covers the
   push step, not the destructive local history rewrite. Appears to be a
   stale one-shot script from an earlier project phase that could be
   accidentally re-run.
6. **(Medium-High)** `scripts/force_stop.py:38` always calls `make down`
   (the full compose pairing) regardless of `--condensed` mode, silently
   mismatching condensed-mode teardown.
7. **(Medium)** `start_app.bat:52-53,80,82` — the `.env`-derived
   `INTERNAL_SERVICE_API_KEY` is spliced into a `cmd /k "set ^"..."` string
   with only caret-escaping of quotes, not shell metacharacters — the same
   bug class as the already-fixed `open-vscode/route.ts` command-construction
   issue, though with lower practical exposure here (the value comes from a
   local `.env` file, not user input).
8. **(Medium-High)** `scripts/restore_postgres.ps1` — performs a destructive
   restore over the live database with no confirmation prompt, no
   pre-restore snapshot, and no manifest/checksum verification of the
   backup being restored.
9. **(Medium)** `scripts/operator_route_auth_matrix_qualification.py:534,539`
   — weak well-known default secrets (`"operator-key"`,
   `"dev-oidc-shared-secret"`) are used to forge bearer tokens if the
   corresponding env vars are unset.
10. **(High mechanism / Medium impact)** `scripts/normalize_document_headers.py`
    — bulk in-place documentation rewrite with no backup or dry-run mode;
    non-atomic, so an abort partway through leaves a mixed state; its
    heuristic can silently delete legitimate content it misclassifies.
11. **(Medium)** `scripts/generate_postgres_tls_certs.py` — no `--force`
    guard (inconsistent with the sibling `generate_agent_service_keys.py`),
    silently regenerates the CA/certificate pair on re-run.
12. **(Medium)** `scripts/rotate_secrets.sh:74-91` — no atomicity across the
    rotation loop; the script's own safety claims overstate what it actually
    guarantees.
13. **(High on fact, low on live impact)** `scripts/dr_drill.ps1` —
    hardcodes `passed = $true` regardless of actual drill outcome. The
    script is self-documented as superseded, but is still wired to
    `make dr-ps1`.
14. **(Medium)** `scripts/run_demo_mission.py:33` — hardcoded placeholder
    fallback API key (`CHANGE_ME_generate_with_openssl_rand_hex_32`). Risk is
    limited to a real deployment that never rotated from this documented
    placeholder value.
15. **(Medium)** `generate_agent_service_keys.py` /
    `generate_postgres_tls_certs.py` — non-atomic multi-file writes; a crash
    mid-write can leave a mismatched cert/key pair on disk.
16. **(Low confidence, bundled)** `build_refined_ir_catalog.py` (silent
    empty-success on a wrong path), `qualification_gate_summary.py` /
    `dora_metrics_summary.py` (broad exception catching can mask corrupt
    evidence), `phase17_release_hardening_evidence.py` (swallows git
    errors), `dedicated_agent_canary_trend.py` (no freshness check, low
    likelihood of mattering), `run_automated_dr_drill.py` (a dead
    `# nosec B602` comment with no corresponding suppressed warning).

**Reviewed with no material findings (~25 scripts):** `check_env.py`,
`generate_build_map.py`, `validate_documentation.py`,
`production_review_audit.py`, `promotion_gate.py`, `backup_postgres.ps1`, and
others in this category. No SQL injection was found anywhere, and no
`shell=True` combined with string-interpolated commands was found in any
Python script reviewed.

---

## 8. Path to a full Windows Electron installer application

This section directly answers the second half of the review request: beyond
bugs, what would it actually take to turn this into a genuine one-click
Windows install/uninstall Electron application, given where the code stands
today. This is a **gap enumeration**, not a remediation plan — no
prioritization, sequencing, or effort estimate is implied here; that belongs
in the separate upgrade plan the user will write after reviewing this
document.

1. **Reconcile the two divergent build modes.** The app currently has two
   incompatible Next.js build outputs: a standalone server (Docker/web-app
   path, `NEXT_BUILD_TARGET=docker`) with full dynamic API routes, and a
   static export (Electron path) that physically cannot contain them and
   currently ships without `app/api/*` at all (§4.3). Before anything else
   about "install/uninstall" matters, the packaged app needs a real answer
   for how vault unlock, session management, mission review/approval, repo
   import, and the gateway proxy are supposed to work when launched as a
   desktop app — e.g., running an embedded Node/Next server inside the
   Electron process instead of a static export, or moving that server-side
   logic into the existing Docker backend and having the Electron renderer
   call it directly.
2. **Give the Electron main process real backend-lifecycle ownership.**
   Today nothing in `electron/` starts, stops, or supervises the Docker
   Compose stack (§4.6) — the app assumes the backend is already running via
   `start_app.bat`. A genuine desktop app needs the main process to
   own that lifecycle: start the compose stack on launch (or detect it's
   already running), show real, blocking status while waiting for it to
   become healthy, and tear it down (or explicitly leave it running, by
   documented design choice) on quit.
3. **Make the Docker-availability check meaningful.** Replace the current
   cosmetic `docker version` check (§4.1-2) with one that verifies the
   actual application containers are up and healthy, and make failure
   actually block the window from loading a UI it cannot use, rather than
   showing a dismissible dialog and proceeding anyway.
4. **Decide and implement a Docker Desktop / WSL2 prerequisite story.** The
   NSIS installer currently has no dependency checks at all (§4.5). A
   real Windows installer needs to either verify Docker Desktop/WSL2 is
   present and guide the user through installing it, bundle/automate that
   setup, or make an explicit, documented decision that this app does not
   support one-click install without a pre-existing Docker environment.
5. **Wire real code signing.** `signtoolOptions.publisherName` is set but
   unused (§4.7) — there is no certificate anywhere in the repo or CI. This
   needs an actual OV or EV Authenticode certificate, `CSC_LINK`/
   `CSC_KEY_PASSWORD` wired into `release.yml`, and — given the post-June-2023
   SmartScreen policy — a decision about whether an OV cert (still shows
   "Unknown Publisher" initially, builds reputation over time) or an EV cert
   (immediate reputation, higher cost) is acceptable for this application's
   distribution model.
6. **Add uninstall disclosure and real cleanup.** `deleteAppDataOnUninstall:
   true` gives a false impression of completeness — it doesn't touch the
   vault at `~/.thefactory/vault.json` (§4.4), and nothing in the uninstall
   path removes Docker containers, images, or volumes created by the app
   (§4.6). A real Windows-style uninstaller needs either custom NSIS
   uninstall hooks that actually clean these up, or a clear, user-facing
   disclosure at uninstall time about what will and will not be removed
   (especially the encrypted vault and any generated mission data/volumes).
7. **Add an auto-start/managed-service option, or explicitly decide against
   one.** Right now there is no way for the packaged app to run as anything
   other than "user manually ensures Docker is running, then launches the
   Electron app." Depending on the desired UX, this could mean a Windows
   service/scheduled task for the backend, an electron-managed background
   process, or a documented decision that this remains a manual two-step
   process even in the packaged form.

**Explicitly not a gap:** the disabled auto-updater (§4.9) is an
intentional, already-documented design decision (manual updates via NSIS
reinstall) — it should not be treated as missing functionality in the
upgrade plan unless the user wants to revisit that decision itself.

---

## 9. Out of scope for this pass

Already reviewed and fixed in earlier phases of this project (not re-reviewed
here): Mission Flow v2 + LLM Delegation, the storage layer, the agent
orchestration core, `api-gateway`, `pod-worker`, verification/compliance
gates, `shared_runtime`, and the Mission Control **API routes**
(`apps/mission-control/app/api/**`, `lib/server/**`) themselves — the latter's
authentication/authorization bugs (vault routes, gateway proxy) were already
found and fixed in commit `8b6d29b`. This review's Electron slice (§4) refers
to those same route files only in the context of the static-export
incompatibility, not their internal logic.
