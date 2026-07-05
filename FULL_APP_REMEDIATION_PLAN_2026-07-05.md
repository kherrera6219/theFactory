# Full-Application Remediation Plan (2026-07-05)

Document version: 2026.07.05
Last updated: 2026-07-05
Status: Active plan — not yet started
Audience: Maintainers and AI coding agents executing the remediation work

**Companion document:** `docs/FULL_APP_CODE_REVIEW_FINDINGS_2026-07-05.md`
is the source of every finding referenced here (file:line evidence,
confidence levels, full per-slice detail). Read that document first if you
need the raw evidence behind any item below — this plan only restates
findings briefly enough to sequence and justify the work; it does not
reproduce the evidence.

This plan turns that read-only review into an ordered, externally-validated
execution sequence. Each phase below cites the specific findings it closes
(by the review doc's §2 executive-summary numbering) and, where a genuine
design decision was needed rather than an obvious bug fix, the external
standard or industry practice that decision is grounded in. Sources
consulted are listed in full in §10.

---

## 1. Guiding principles

These four principles, each validated against current external guidance,
govern every phase below:

1. **Fail secure, not fail open, on production configuration.** OWASP's
   Top 10 category for security misconfiguration explicitly calls out
   "default credentials left in place" and "missing CORS controls" as the
   representative failure mode this plan's Phase 0 findings match exactly
   ([OWASP Top 10:2025 — A02 Security Misconfiguration](https://owasp.org/Top10/2025/A02_2025-Security_Misconfiguration/)).
   The remediation pattern — a startup-time guard that raises rather than
   warns when a production environment is detected running an insecure
   default — is not a new invention for this codebase; it is the same
   pattern already used correctly by the adjacent CORS-wildcard check in
   `api_gateway/main.py:1660-1661`. Phase 0 makes the rest of the
   codebase consistent with that existing precedent.
2. **Destructive operations default to safe, not to destructive.** The
   industry-standard shape — popularized by Terraform's `plan`/`apply`
   split, Ansible's `--check` mode, and Kubernetes' `--dry-run=client` — is
   that a script capable of doing real damage should require an explicit
   opt-in flag to actually do it, not an explicit opt-out
   ([Dry-Run Engineering: The Simple Practice That Prevents Production Disasters](https://dev.to/danieljglover/dry-run-engineering-the-simple-practice-that-prevents-production-disasters-ek0);
   [Google SRE Book — Production Services](https://sre.google/sre-book/service-best-practices/)).
   Every scripts-slice finding in Phase 1 that involves data loss or live
   mutation is remediated by inverting its default to this shape.
3. **Reconcile, don't multiply, build/runtime paths.** The Electron
   packaging problem is fundamentally a design decision, not a bug — the
   current split between a Docker-hosted standalone Next.js server and a
   static-export Electron build is exactly the failure mode the wider
   Next.js/Electron community has already converged on a standard answer
   for: run the same standalone server *inside* Electron rather than
   maintaining two build targets
   ([Building an Electron App with Next.js — DoltHub](https://www.dolthub.com/blog/2024-09-11-building-an-electron-app-with-nextjs/);
   [The ultimate Electron app with Next.js and React Server Components](https://dev.to/kirillkonshin/the-ultimate-electron-app-with-nextjs-and-react-server-components-1b7g);
   [How I Build a Desktop App with Next.js + Electron — Without Static Export](https://asrulkadir.medium.com/this-is-how-i-build-a-desktop-app-with-next-js-electron-without-static-export-59d68c96d11f)).
   Phase 4 adopts this as the core architectural decision, since it
   simultaneously resolves the build-mode split and the broken-API-routes
   finding with one change instead of two.
4. **Windows code signing should target Azure Trusted Signing (now Azure
   Artifact Signing), not an EV certificate.** This is a real, recent
   (2024) change to Microsoft's own policy that invalidates older
   conventional wisdom: EV certificates no longer bypass SmartScreen on
   first download — both EV and OV certificates now build reputation the
   same way, through download history, so paying the EV premium no longer
   buys instant trust
   ([Microsoft Learn — SmartScreen reputation for Windows app developers](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation);
   [Microsoft Learn — Code signing options for Windows app developers](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options);
   [Transitioning from EV Certificate to Azure Trusted Signing — electron-builder #8696](https://github.com/electron-userland/electron-builder/issues/8696)).
   Given this app's distribution model (small team, US-based, CI/CD-driven
   releases via GitHub Actions), Azure Artifact Signing is both cheaper and
   integrates directly into `release.yml` without a hardware token
   ([How to Sign a Windows App with Electron Builder — Security Boulevard](https://securityboulevard.com/2025/12/how-to-sign-a-windows-app-with-electron-builder/)).

---

## 2. Sequencing rationale

Phases are ordered by **blast radius of inaction versus cost to fix**, not
by which slice they came from:

- **Phase 0** first: these are live, running-today security defaults with
  no architectural dependency on anything else — cheapest fixes with the
  highest current real-world exposure (production RQCA enforcement
  silently off, production object storage on default credentials).
- **Phase 1** second: these are tooling/operator-safety guardrails.
  They're independent of Phase 0-2, but should land before any other phase
  touches infrastructure (DB restores, container rebuilds), since several
  later phases will themselves run these same scripts.
- **Phase 2** third: contained, low-risk frontend fixes with no
  architecture decisions attached. Deliberately sequenced *before* Phase 4
  so that Phase 4's Electron rebuild inherits all of these fixes for free
  once the build-mode reconciliation happens, instead of needing a second
  pass.
- **Phase 3** (documentation accuracy) can run in parallel with any other
  phase — it has no code dependencies. Listed after Phase 2 only for
  narrative order.
- **Phase 4** (Electron/Windows installer) last: the only phase requiring
  a genuine architecture decision and a full rebuild/re-signing/re-release
  cycle. Doing it last means the packaged app picks up every other phase's
  fixes in the same rebuild, rather than requiring its own separate
  remediation pass afterward.

---

## 3. Phase 0 — Harden production runtime defaults

**Closes findings #1, #2, #18, #23, #26** (review doc §2/§5/§6). No
architecture decisions required; all four are configuration/guard changes
following an already-established pattern in this codebase.

1. **`RQCA_ENFORCEMENT_ENABLED` compose default** (review doc §6 finding 1,
   `deploy/docker-compose.yaml:326`). Remove the `:-false}` fallback (or
   change it to `:-true}`) so the compose layer stops silently overriding
   the hardened code-level default set earlier this project
   (`services/orchestrator/orchestrator/settings.py:373-375`). Add a
   startup-time guard, mirroring the existing CORS-wildcard check pattern
   in `api_gateway/main.py:1660-1661`, that raises if
   `ENVIRONMENT=="production"` and this flag resolves to `false` — a
   compose-file edit alone isn't sufficient protection against a future
   `.env` override reintroducing the same bug.
2. **Production MinIO credentials** (review doc §6 finding 2,
   `deploy/docker-compose.yaml:222,289-290`). Add explicit credential
   overrides to `docker-compose.prod.yaml` (no default fallback in the prod
   overlay) and add an application-level fail-fast check at startup that
   refuses to boot if the resolved credentials equal the literal
   `minioadmin`/`minioadmin123` strings while `ENVIRONMENT=="production"` —
   same "default credentials left in place" failure mode OWASP explicitly
   calls out (see §1.1 above).
3. **`GATEWAY_ADMIN_BYPASS` inconsistent enforcement** (review doc §6
   finding 5, `api_gateway/main.py:1663-1667`). Change the warn-only branch
   to raise `RuntimeError` in production, exactly matching the adjacent
   CORS-wildcard check three lines above it. This closes an inconsistency,
   not a design gap — the correct pattern already exists two lines away in
   the same file.
4. **`CORS_ALLOW_ORIGINS` hardcoded to `localhost:3100`** (review doc §6
   finding 3). Make this environment-configurable per deployment target and
   add an explicit, documented production value to
   `docker-compose.prod.yaml` rather than relying on the base file's dev
   default. Not a vulnerability (the wildcard case already fails fast) but
   an operational-correctness gap that belongs in the same pass since it
   touches the same file/review area.
5. **`agent-runtime` `SERVICE_API_KEY` weak default** (review doc §5
   finding 1, `services/agent-runtime/agent_runtime/main.py:53`). Remove
   the `"worker-key"` fallback; require the env var to be set, failing
   fast at process start if it is not — same remediation shape as #2 above.

**Exit criteria:** full backend test suite passing, `ruff check` clean,
`docker compose config` merge re-verified to confirm no profile still
resolves an insecure default, all four affected images rebuilt and the new
guards verified inside the rebuilt containers (matching this project's
established verification bar from every prior review pass).

---

## 4. Phase 1 — Script and tooling safety guardrails

**Closes findings #6, #7, #8, #9, #10, #19, #20, #24, #25, #27, #29**
(review doc §7). Every item here follows the dry-run-by-default principle
from §1.2 above.

1. **`Makefile` duplicate `demo:` target** (finding #10,
   `Makefile:88-90` vs. `195-196`). Delete the shadowing duplicate; keep
   the one that calls `demo_missions.py --dry-run`.
2. **`run_automated_dr_drill.py` real-drill default** (finding #6, line 96).
   Invert the flag: require an explicit `--execute`/`--i-understand-this-deletes-data`
   flag to run the destructive `docker compose down -v` path; dry-run
   becomes the default with no flag needed.
3. **`operator_route_auth_matrix_qualification.py` /
   `langgraph_postgres_recovery_qualification.py`** (finding #7). Same
   inversion — default to a dry-run/plan-only mode that prints what would
   be force-recreated/rebuilt and what auth mode would be flipped, requiring
   an explicit confirmation flag to actually mutate live containers or
   auth config.
4. **`execute_git_history_scrub.ps1`/`.py`** (finding #8). This script
   predates `git-filter-repo`'s own safety model and should be brought in
   line with it: `git-filter-repo` itself refuses to run outside a fresh
   clone specifically to guarantee an unmodified backup exists
   ([git-filter-repo — GitHub](https://github.com/newren/git-filter-repo);
   [Git Filter-Repo: The Best Way to Rewrite Git History](https://www.git-tower.com/learn/git/faq/git-filter-repo)).
   Remove the `--force` override if present, require the working tree to be
   a fresh clone (the tool's own default behavior), and add an explicit
   `--dry-run`/preview mode before the destructive local rewrite step (not
   just before the push step, which is already gated).
5. **`OPERATIONS_RUNBOOK.md` self-contradiction** (finding #9, lines
   223-230). Fix the recovery-steps section to use the paired compose-file
   form it warns about elsewhere in the same document.
6. **`force_stop.py` condensed-mode mismatch** (finding #20, line 38) and
   **the `--condensed` profile's structural fragility** (finding #24).
   Make `force_stop.py` detect condensed mode and tear down the matching
   single-file form; document the intentional single-file design for
   condensed mode directly in the compose file itself (a comment banner) so
   future edits can't silently assume the paired form applies universally.
7. **`restore_postgres.ps1`** (finding #19). Add a required confirmation
   prompt (or `--yes` flag) before restoring over a live database, plus a
   pre-restore snapshot and a manifest/checksum check of the backup being
   restored — same dry-run-by-default shape applied to a restore instead of
   a delete.
8. **Weak well-known default secrets in qualification scripts** (finding
   #25, `operator_route_auth_matrix_qualification.py:534,539`). Require
   these env vars to be set explicitly with no fallback, same remediation
   as Phase 0 item 5, but lower urgency since this is qualification tooling
   rather than the live runtime.
9. **`normalize_document_headers.py`** (finding #27). Add a `--dry-run`
   mode that reports planned changes without writing, and make the actual
   write path atomic per file (write-to-temp + rename, the same pattern
   already used correctly by `shared_runtime/atomic_io.py`).
10. **Remaining lower-severity items bundled here** (finding #29):
    `generate_postgres_tls_certs.py` — add a `--force` guard matching its
    sibling `generate_agent_service_keys.py`; both cert generators — make
    multi-file writes atomic; `rotate_secrets.sh` — either fix the
    atomicity gap across the rotation loop or correct its safety claim to
    match actual behavior; `dr_drill.ps1` — remove the hardcoded
    `passed = $true` or retire the script outright since it is already
    self-documented as superseded; `run_demo_mission.py` — fail fast
    instead of silently falling back to the placeholder API key.

**Exit criteria:** each changed script's existing test/smoke coverage
passing; a manual dry-run invocation of each destructive script confirmed
to make zero live changes by default; `scripts/validate_documentation.py`
passing after the runbook fix.

---

## 5. Phase 2 — Frontend UI correctness, accessibility, and data-integrity fixes

**Closes findings #3, #11, #12, #13, #14, #21, #22**, plus the CSP
`script-src 'unsafe-inline'` item and the `global-search.tsx` dead-code
cleanup noted in review doc §4 finding 11 and §3 item 8 respectively.

1. **Alerts don't persist** (finding #3, `alerts/page.tsx:81-92,168-172`).
   Wire "Acknowledge"/"Mark Resolved" to a real backing API call so state
   survives a refresh; this is a straightforward missing-integration fix,
   not a design decision.
2. **Stale-response races** (finding #11,
   `useArtifactData.ts:31-54`, `missions/detail/page.tsx:127-160`,
   `missions/page.tsx:158-184,230-238,254-271`). Add request
   cancellation/generation-guards (an `AbortController` per request, or a
   monotonically increasing request-id compared on resolution) to every
   affected fetch site so a stale response from a previous mission can
   never render under a new mission's header.
3. **Non-semantic clickable `<div>`s** (finding #12,
   `missions/output/page.tsx:125-156`, `protocol-bus/page.tsx:463`). Apply
   the existing correct pattern already used in `FileTreePane.tsx:59-94`
   (`role`, `tabIndex`, `onKeyDown`) to both locations.
4. **Guided-tour keyboard trap** (finding #13,
   `guided-tour.tsx:213-221`). Add the same `.focus()`-on-open call already
   used correctly by `KeyboardShortcuts`/`DialogProvider`.
5. **Literal unicode escape rendering as raw text** (finding #14,
   `missions/detail/page.tsx:455`). Quote the string, matching lines 493
   and 603 in the same file.
6. **Chat session retention** (finding #21, `chat/page.tsx:82-84,652-680`).
   Decide and implement a retention policy (cap age/count more
   aggressively, or encrypt at rest using the same vault-adjacent pattern
   already used elsewhere in this app) — flagged as a decision point since
   the review found no active exploit, only an unbounded-retention gap.
7. **Inconsistent 401/403 handling and dead `unlock` stub** (finding #22).
   Extract the working heuristic from `chat/page.tsx:203-220`
   (`isOperatorAuthError()`) into a shared hook applied consistently across
   pages, and either wire `app/unlock/page.tsx` into a real flow or remove
   it if superseded.
8. **CSP `script-src 'unsafe-inline'`** (review doc §4 finding 11,
   `app/layout.tsx:30-44`). Investigate why inline scripts are required
   (most likely Next.js's own hydration/RSC bootstrap script). If so,
   Next.js's own guidance is to generate a per-request nonce (via
   middleware) and thread it through rather than allow all inline scripts
   unconditionally; note that this requires opting into dynamic rendering
   and disables static optimization for the affected routes, which is a
   real trade-off given this app's Electron static-export path depends on
   static generation today (see Phase 4) —
   ([Next.js — Content Security Policy guide](https://nextjs.org/docs/app/guides/content-security-policy);
   [Next.js CSP: Static Pages, Nonces and Trade-offs](https://johnkavanagh.co.uk/articles/content-security-policy-in-nextjs/)).
   If Phase 4's embedded-server approach is adopted (dynamic rendering
   already required), a nonce-based CSP becomes straightforward and should
   be revisited then rather than solved twice.
9. **`global-search.tsx` dead code** (review doc §3, "reviewed with no
   material findings"). Confirm it is fully superseded by
   `command-palette.tsx` and remove it.

**Exit criteria:** Mission Control focused Vitest suite passing, `npm run
build`/`lint`/`tsc --noEmit` clean, a manual keyboard-only pass through the
guided tour and the two fixed clickable-row components, and a manual
fast-navigation test across missions to confirm the stale-response fix.

---

## 6. Phase 3 — Documentation accuracy follow-ups

**Closes findings #15, #28.**

1. **`docs/METRICS_SOURCE_MODULES.md` incomplete inventory** (finding #15).
   Add the four omitted metrics: `pod_worker_task_latency_seconds`,
   `agent_runtime_task_latency_seconds`, `audit_worker_task_latency_seconds`,
   `factory_llm_tokens_total`.
2. **Stale lowercase mission-state casing** (finding #28,
   `orchestrator_metrics.py:57` comment and
   `docs/METRICS_SOURCE_MODULES.md:19`). Fix both to the real uppercase
   values (`QUEUED`/`RUNNING`/`VERIFIED`).

**Exit criteria:** `scripts/validate_documentation.py` passing.

---

## 7. Phase 4 — Electron/Windows installer buildout

This is the only phase requiring genuine architecture decisions rather than
straightforward bug fixes. Ordered as a dependency chain — each sub-phase
below assumes the previous one is done, since 4.1 is the prerequisite for
everything else in this phase to be meaningful.

### 4.1 — Reconcile the two build modes (closes finding #4, the single most significant finding in the whole review)

**Decision, validated against current community practice (§1.3):** replace
static export for the Electron build with the same `output: 'standalone'`
Next.js server the Docker/web-app path already runs, launched as a child
process from the Electron main process on a dynamically chosen local port,
with the `BrowserWindow` loading `http://localhost:<port>` instead of a
`file://` static bundle. This is the pattern the wider community has
already converged on for exactly this problem
([DoltHub — Building an Electron App with Next.js](https://www.dolthub.com/blog/2024-09-11-building-an-electron-app-with-nextjs/);
[Medium — The ultimate Electron app with Next.js and React Server Components](https://medium.com/@kirill.konshin/the-ultimate-electron-app-with-next-js-and-react-server-components-a5c0cabda72b)).
Concretely:

- Remove the `NEXT_BUILD_TARGET`-gated `output: "export"` branch in
  `next.config.mjs` for the Electron target; both build targets converge on
  the standalone server output.
- Delete `scripts/build-electron.mjs`'s `app/api` hide/restore step — it
  becomes unnecessary once the API routes are actually served.
- All 14 `app/api/*` routes become functional in the packaged app for free,
  since they're the same routes the web-app path already serves correctly.
- This also resolves the CSP `unsafe-inline`/nonce trade-off flagged in
  Phase 2 item 8 — dynamic rendering is now required anyway for the
  Electron path, so a nonce-based CSP has no additional static-optimization
  cost to weigh against it.
- Known trade-off to accept, not a blocker: static export currently avoids
  bundling a Node runtime inside the Electron app; the standalone-server
  approach requires shipping Node (which Electron already embeds) and
  managing a child-process lifecycle — directly addressed by 4.2.

### 4.2 — Give the Electron main process real backend-lifecycle ownership (closes part of finding #4/#16)

The main process must now supervise two things it didn't before: the
embedded standalone Next.js server (from 4.1) and the Docker Compose
backend it depends on. Concretely: spawn/monitor the Next.js server
child process on app launch and terminate it on quit; on
`window-all-closed` (`electron/main.ts:202-206`), decide and implement
whether the Docker backend should also be torn down or left running (a
product decision, not inferred from existing code — flag for the user to
confirm before implementing).

### 4.3 — Make the Docker-availability check meaningful (closes finding #16)

Replace `checkDockerAvailability()`'s `docker version` reachability check
with one that verifies the actual application containers are up and
healthy (e.g., polling the orchestrator's existing `/readyz` endpoint,
already used elsewhere in this codebase for the same purpose). Make
failure genuinely block window creation rather than showing a dismissible,
non-blocking dialog before proceeding anyway (`electron/main.ts:115-131`).

### 4.4 — Decide and implement a Docker Desktop / WSL2 prerequisite story

Research confirms electron-builder has no built-in prerequisite-checker
feature for arbitrary external software
([NSIS — electron-builder docs](https://www.electron.build/nsis.html)) — this
must be custom-built via a `preInit`/`customInit` macro in
`build/installer.nsh` (the standard extension point electron-builder
provides for exactly this kind of installer customization
([NSIS — electron-builder docs](https://www.electron.build/nsis.html);
[Creating a custom NSIS include — electron-builder #1231](https://github.com/electron-userland/electron-builder/issues/1231))),
shelling out to check for Docker Desktop/WSL2 and guiding the user to
install it if absent, or explicitly documenting that this app requires a
pre-existing Docker environment and does not attempt to install one. This
is a product decision the plan flags rather than resolves — pick one before
implementing.

### 4.5 — Wire real code signing (closes finding #5)

Per §1.4 above: use Azure Artifact Signing (formerly Azure Trusted
Signing) rather than purchasing an EV certificate, since the 2024
SmartScreen policy change means EV no longer buys instant trust over OV —
both now build reputation identically through download history
([Microsoft Learn — SmartScreen reputation](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)).
Azure Artifact Signing integrates directly into `release.yml` via GitHub
Actions with no hardware token requirement, and is available to individual
US/Canada developers or EU/UK organizations
([How to Sign a Windows App with Electron Builder — Security Boulevard](https://securityboulevard.com/2025/12/how-to-sign-a-windows-app-with-electron-builder/)).
Update `package.json`'s `signtoolOptions` and `release.yml`'s
`electron:package` step accordingly; remove the stale
`# Future: CSC_LINK and CSC_KEY_PASSWORD` comment once real signing lands.

### 4.6 — Add uninstall disclosure and real cleanup (closes finding #17)

Using the same `build/installer.nsh` extension point as 4.4
(`customInstall`/`customUnInstall` macros
([NSIS — electron-builder docs](https://www.electron.build/nsis.html))):
add an uninstall-time dialog disclosing that the vault
(`~/.thefactory/vault.json`) and any Docker containers/images/volumes
created by the app are not touched by the default uninstall, with an
opt-in cleanup path for users who want a full removal. Do not silently
delete the vault by default — that would be a data-loss surprise in the
other direction.

### 4.7 — Auto-start/managed-service decision

Explicitly decide (flagged for user input, not inferred): does the
packaged app get a Windows service/scheduled task for the backend, an
Electron-managed background process, or does it remain the current
"user ensures Docker is running, then launches the app" two-step flow?
This has no forced answer from the research above — it is a UX/product
scope decision, not a technical best-practice question.

**Explicitly not in scope for this phase:** the disabled auto-updater
(review doc §4 item 9) is an intentional, already-accepted design decision
and should not be revisited as part of this plan unless the user separately
asks to.

**Exit criteria:** a packaged build where all 14 API routes function
identically to the web-app path (verified by exercising vault
unlock/session/mission-review flows inside the packaged app, not just the
browser tab); a signed installer that no longer shows "Unknown Publisher";
an uninstall that discloses and offers cleanup of the vault and Docker
resources; full existing Mission Control test suite plus a new
Electron-specific smoke pass.

---

## 8. Cross-phase exit criteria

Every phase, regardless of size, is expected to meet the verification bar
already established throughout this project's prior review work: full
relevant test suite passing, `ruff check`/`tsc --noEmit`/lint clean on
touched files, a regression test proven to fail against the pre-fix code
via `git stash` for any behavioral bug fix, affected Docker images rebuilt
and fixes verified inside the rebuilt container (not just locally), and
`scripts/validate_documentation.py` passing for any doc change.

---

## 9. Explicit non-goals of this plan

- This plan does not implement anything — it is a sequencing and
  justification document, to be executed phase by phase in separate work
  sessions.
- Product-scope decisions are flagged, not made, in §7.2, §7.4, and §7.7 —
  these need explicit user sign-off before implementation, not an assumed
  default.
- The auto-updater (already intentionally disabled) is out of scope
  entirely, per review doc §4 item 9.
- No phase here revisits already-fixed findings from prior review passes
  (Mission Flow v2, storage layer, orchestration core, api-gateway,
  pod-worker, verification/compliance gates, `shared_runtime`, Mission
  Control API routes) — those are closed.

---

## 10. References consulted

- [OWASP Top 10:2025 — A02 Security Misconfiguration](https://owasp.org/Top10/2025/A02_2025-Security_Misconfiguration/)
- [Dry-Run Engineering: The Simple Practice That Prevents Production Disasters](https://dev.to/danieljglover/dry-run-engineering-the-simple-practice-that-prevents-production-disasters-ek0)
- [Google SRE Book — Production Services Best Practices](https://sre.google/sre-book/service-best-practices/)
- [git-filter-repo (GitHub)](https://github.com/newren/git-filter-repo)
- [Git Filter-Repo: The Best Way to Rewrite Git History](https://www.git-tower.com/learn/git/faq/git-filter-repo)
- [Building an Electron App with Next.js — DoltHub](https://www.dolthub.com/blog/2024-09-11-building-an-electron-app-with-nextjs/)
- [The ultimate Electron app with Next.js and React Server Components](https://medium.com/@kirill.konshin/the-ultimate-electron-app-with-next-js-and-react-server-components-a5c0cabda72b)
- [This is How I Build a Desktop App with Next.js + Electron — Without Static Export](https://asrulkadir.medium.com/this-is-how-i-build-a-desktop-app-with-next-js-electron-without-static-export-59d68c96d11f)
- [Microsoft Learn — SmartScreen reputation for Windows app developers](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation)
- [Microsoft Learn — Code signing options for Windows app developers](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
- [Transitioning from EV Certificate to Azure Trusted Signing — electron-builder #8696](https://github.com/electron-userland/electron-builder/issues/8696)
- [How to Sign a Windows App with Electron Builder — Security Boulevard](https://securityboulevard.com/2025/12/how-to-sign-a-windows-app-with-electron-builder/)
- [NSIS — electron-builder documentation](https://www.electron.build/nsis.html)
- [Creating a custom NSIS include — electron-builder #1231](https://github.com/electron-userland/electron-builder/issues/1231)
- [Next.js — Content Security Policy guide](https://nextjs.org/docs/app/guides/content-security-policy)
- [Next.js CSP: Static Pages, Nonces and Trade-offs](https://johnkavanagh.co.uk/articles/content-security-policy-in-nextjs/)
- [Docker Secrets Explained: Setup, Best Practices & Examples — Wiz](https://www.wiz.io/academy/container-security/docker-secrets)
- [Manage secrets securely in Docker Compose — Docker Docs](https://docs.docker.com/compose/how-tos/use-secrets/)
