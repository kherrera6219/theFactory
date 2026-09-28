# Windows Installer and Desktop App

Document version: 2026.09.27
Status: Implemented and validated end to end on Windows (WQ #9); first public release pending
Audience: Maintainers, release managers, operators

`theFactory-MissionControl-Setup-<version>.exe` installs Mission Control as a
normal Windows application. The factory itself -- orchestrator, gateway,
workers, data stores, sandbox runners -- runs in Docker Desktop; the app
installs, starts, monitors, stops and removes it.

## Operator decisions (2026-09-27)

These close WORK_QUEUE #9's sign-off gate and are not open questions.

| # | Decision | Chosen |
|---|---|---|
| E1 | Closing the window | **Keep running in the tray.** Missions are never interrupted by closing a window. The tray offers *Quit (factory keeps running)* and *Quit and stop factory*. |
| E2 | Docker Desktop | **Check and guide.** The installer and the app detect Docker Desktop and WSL 2, explain what is missing, link to Docker's own installer, and re-check. theFactory never installs third-party software. |
| E3 | Start with Windows | **Off by default, opt-in** -- a checkbox on the installer's finish page and in the tray menu. Starts in the tray only (`--hidden`). |
| E4 | Backend images | **Public GHCR images**, version-tagged per release. Small installer; the first launch downloads the services with a progress window. |
| E5 | Uninstall | **Keep data by default.** *Remove everything* is a separate, twice-confirmed choice because the data includes audit evidence under legal hold. |

## What the user sees

### Install

1. **Welcome**, then **licence**.
2. **Install location** -- per-user by default (`%LOCALAPPDATA%\Programs`), changeable; no admin rights needed unless the user picks a protected folder.
3. **Prerequisites** (custom page) -- live status of Docker Desktop (running / installed-not-running / not installed) and WSL 2, with *Get Docker Desktop* and *Re-check* buttons. The user may continue without Docker; the app checks again on first launch.
4. **Installing** -- standard progress bar with details.
5. **Finish** -- *Launch theFactory Mission Control now* (checked) and *Start theFactory when Windows starts* (unchecked).

### First launch

A status window shows five steps with a progress bar and a live log:

| Step | What happens |
|---|---|
| Check Docker Desktop | If missing or stopped: a dialog explains, offers Docker's download page, *Retry*, or *Quit*. |
| Prepare configuration | First run only: the AI-provider key wizard, then a private `backend.env` with freshly generated secrets. Every run: TLS certificates, the image tag, and the sandbox workspace path are refreshed. |
| Download factory images | Each image is pulled if absent -- *Downloading image 4 of 14* -- then the sandbox runners are tagged with the names runtime QC uses. |
| Start services | `docker compose up -d --no-build` under the project name **`thefactory-app`**. |
| Wait for healthy | Polls the gateway's `/readyz`. |

The window has *Open logs folder* and *Run in background*. Everything is also
written to `%APPDATA%\theFactory Mission Control\Logs\factory.log`.

### Every day

- Closing the window hides it; a one-time notification says the factory is still running.
- The tray tooltip and first menu line show **Factory running / starting / stopped / not reachable**, polled every 15 s.
- Tray menu: open Mission Control, New Mission, View Missions, *Show factory status*, *Start factory*, *Stop factory*, *Open logs folder*, *Start with Windows*, *Quit (factory keeps running)*, *Quit and stop factory*.
- Launching the app again while it runs brings the existing window forward (single instance).

### Uninstall (Settings > Apps, or the Start-menu uninstaller)

1. **Welcome**.
2. **Your factory data** (custom page):
   - **Keep my data (recommended)** -- stops and removes the containers; missions, settings, vault and audit evidence stay, and a reinstall picks them up.
   - **Remove everything** -- also deletes all factory volumes and images. A second warning names the audit evidence under legal hold; *No* returns to the page.
3. **Uninstalling** -- the progress log shows each step from the maintenance helper, e.g. `[1/15] Removing the thefactory-app containers and ALL factory data volumes... done`.
4. **Finish**.

Silent uninstall (`/S`) keeps data. An *update* runs the old uninstaller
silently and never touches the stack.

## How it works

| Piece | File |
|---|---|
| Stack contract shared by app and uninstaller (project name, compose argv, image list, progress bands) | `apps/mission-control/electron/factory-stack.ts` |
| Uninstall helper, run under plain Node (`ELECTRON_RUN_AS_NODE=1`) from `resources\maintenance` | `apps/mission-control/electron/maintenance.ts` |
| Startup pipeline, tray lifecycle, single instance, Start with Windows | `apps/mission-control/electron/main.ts`, `tray.ts` |
| Status / progress window | `apps/mission-control/electron/starting.html`, `starting-preload.ts` |
| Per-start `.env` refresh that preserves secrets | `apps/mission-control/electron/env-generator.ts` (`upsertEnvValues`) |
| Custom NSIS pages and hooks | `apps/mission-control/build/installer.nsh` |
| Published-image overlay | `deploy/docker-compose.installer.yaml` |
| Image publishing and version stamping | `.github/workflows/release.yml` |

Three properties are guarded by tests:

- **The installed app never shares a compose project with a developer
  checkout.** Compose derives the project name from the `deploy/` directory in
  both layouts, so without `--project-name thefactory-app` an uninstall's
  `down --volumes` could delete a developer's own stack.
- **No service is built from source on a user machine**
  (`test_installer_overlay_replaces_every_build_context`), and **every image the
  app pulls is published by the release**
  (`test_release_publishes_every_image_the_installed_app_pulls`).
- **Keeping data keeps the key to it.** `backend.env` holds the passwords of
  the kept volumes, so the default uninstall keeps app data; only *Remove
  everything* deletes it.

## Releasing

1. Tag `vX.Y.Z` on `main`. `release.yml` (behind the `staging` and
   `production` environments) publishes 14 images as
   `ghcr.io/kherrera6219/thefactory-*:vX.Y.Z` and `:latest`, stamps the app
   version to `X.Y.Z`, builds the installer and attaches it to the GitHub
   release.
2. **One-time, per package, by the owner:** make each
   `thefactory-*` package **public** (GitHub > Packages > package > Settings >
   Change visibility). Until then anonymous pulls return 403 and a user's first
   launch fails at *Download factory images* with that error in the log.
3. **Code signing** (recommended before wide distribution): add `CSC_LINK` and
   `CSC_KEY_PASSWORD` secrets for an Authenticode certificate. Unsigned
   installers work but Windows SmartScreen warns about an unknown publisher.

## Testing

- `npx vitest run electron` -- stack contract, maintenance helper, env upsert, tray menu.
- `pytest tests/services/test_installer_overlay.py` -- overlay and release coverage.
- `npm run electron:package` builds `dist/installers/theFactory-MissionControl-Setup-<v>.exe`;
  NSIS warnings are errors.
- Silent install/uninstall smoke: `Setup.exe /S /D=<dir>`, then
  `"<dir>\Uninstall theFactory Mission Control.exe" /S` -- keeps data by design.

## Verification record (2026-09-27)

| Check | Result |
|---|---|
| `npm run electron:package` | `theFactory-MissionControl-Setup-0.1.0.exe` (~174 MB); NSIS warnings are errors, both passes clean; build fails if a sandboxed preload requires anything but `electron` |
| Install (per-user, `/S /currentuser`) | exit 0, no UAC; app under `%LOCALAPPDATA%\Programs`, **desktop icon** and Start-menu entry created; no autostart value (opt-in) |
| Launch from the desktop icon | Mission Control renders with minimize / maximize / close; content starts below the titlebar; home page shows live missions and gateway READY, Redis and orchestrator HEALTHY |
| Second launch | brings the running window forward (single instance); closing hides to the tray |
| Maintenance helper via installed exe (`ELECTRON_RUN_AS_NODE=1`) | `stop` / `down` against project `thefactory-app` exit 0 with per-step progress; bad action exit 2; developer `deploy` stack untouched |
| Uninstall (silent) | exit 0; files, registry entry, Start-menu and desktop shortcuts removed; developer stack untouched |
| Interactive all-users uninstall (operator) | completed after UAC approval; Program Files clean |
| Unit tests | Vitest 201/201; `test_installer_overlay.py` 4/4 |

Local validation note: on the development machine the installed app attaches to
the already-running dev stack on :8100, so for validation its `backend.env` was a
copy of the repository `.env` (the keys that stack runs with). A real install
generates its own.

## Defects found by installing and running the app (all fixed)

| # | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | Installed app crashed on launch: `spawn ...\theFactory Mission Control.exe ENOENT` | The embedded Next.js server was spawned with its working directory **inside `app.asar`**, an archive file a process cannot use as a cwd; the spawn error was unhandled | `asarUnpack: .next/standalone/**`; the server is resolved from `app.asar.unpacked`; a spawn failure is reported instead of crashing |
| 2 | No minimize / maximize / close; first-run wizard could not submit; status window never updated | All three preload scripts `require`d a local module, which a **sandboxed** preload cannot load, so `window.electronAPI` never existed | Preloads bundled with esbuild into self-contained files; the build fails if one requires anything but `electron` |
| 3 | Titlebar covered the page header and brand | Shell, sidebar and main column are `100vh`; padding pushed their tops under the fixed titlebar | Sidebar and main column sized to `100vh - titlebar` when the titlebar is mounted |
| 4 | "Mission metrics are unavailable" on a working stack | The embedded server received none of the Mission Control container's keys or URLs | `embeddedServerEnv()` passes the same secrets, host-side gateway/orchestrator URLs, and a vault path in the app's data folder |
| 5 | Saved provider keys would not persist on a fresh install | Generated secrets were 24 bytes; the vault's AES-256 key must be exactly 64 hex chars | All generated secrets are 32 bytes (what `.env.example` asks for) |
| 6 | Logs / data in `%APPDATA%\mission-control`, not where docs and the uninstaller look | Electron named userData after package `name` | userData pinned to `%APPDATA%\theFactory Mission Control` |

The install-mode page pre-selecting *all users* is electron-builder's upgrade
behaviour: it keeps the mode of an existing machine-wide install it finds under
`HKLM\Software\<app GUID>`. On a clean machine the default is *Only for me*
(verified: `/currentuser` installs need no UAC).

Model: all agents default to **`gemini-3.8-flash`** (2026-09-27). A vault slot
still pinned to 3.5 / 3.6 / 3.7 migrates to 3.8 on read.
