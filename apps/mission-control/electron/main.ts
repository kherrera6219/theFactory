import { spawn, type ChildProcess } from "child_process";
import fs from "fs";
import { createServer } from "net";
import path from "path";
import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import { setupTray } from "./tray";
import { setupUpdater } from "./updater";  // version IPC only — auto-update disabled
import { installCrashHandlers, generateDiagnostics } from "./diagnostics";
import { IPC_CHANNELS } from "../app/lib/electron-bridge";
import { ensureTlsCertificates } from "./tls-certs";
import { generateEnvFile, type LlmProviderKeys } from "./env-generator";
import { SETUP_WIZARD_CHANNELS, STARTING_WINDOW_CHANNEL } from "./wizard-ipc-channels";

// A8 — install application-boundary crash handlers before anything else can throw.
installCrashHandlers();

const isDev = process.env.ELECTRON_DEV === "1";
const isE2E = process.env.ELECTRON_E2E === "1";
const NEXT_DEV_PORT = 3100; // Match next dev --port in package.json
const GATEWAY_READYZ_URL =
  process.env.MISSION_CONTROL_GATEWAY_READYZ_URL?.trim() || "http://localhost:8100/readyz";
// Auto-starting the bundled backend involves pulling ~9 images plus base
// infra images on first run -- give it several minutes before falling back
// to the manual retry/quit dialog.
const BACKEND_STARTUP_TIMEOUT_MS = 20 * 60 * 1000;

let mainWindow: BrowserWindow | null = null;
let embeddedServerProcess: ChildProcess | null = null;

// ── Embedded standalone Next.js server (packaged/production only) ──────────
// Electron previously loaded a static export (`out/index.html`), which
// physically cannot serve any of this app's app/api/* routes (vault, session,
// gateway proxy, repo import, etc.) -- see
// docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md §7.1. This spawns the same
// `output: "standalone"` Next.js server the build produces (see
// scripts/build-electron.mjs) as a child process on a free local port and
// loads that instead, matching the community-standard Next.js-in-Electron
// pattern -- all API routes work for real now.

function findFreePort(): Promise<number> {
  return new Promise((resolve, reject) => {
    const probe = createServer();
    probe.unref();
    probe.on("error", reject);
    probe.listen(0, "127.0.0.1", () => {
      const address = probe.address();
      if (address && typeof address === "object") {
        const { port } = address;
        probe.close(() => resolve(port));
      } else {
        probe.close(() => reject(new Error("Unable to determine a free port")));
      }
    });
  });
}

function standaloneServerPath(): string {
  const candidates = [
    path.join(app.getAppPath(), ".next", "standalone", "server.js"),
    path.join(process.cwd(), ".next", "standalone", "server.js"),
  ];
  return candidates.find((candidate) => fs.existsSync(candidate)) ?? candidates[0];
}

async function waitForServerReady(url: string, timeoutMs = 20_000): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.status < 500) {
        return true;
      }
    } catch {
      // Not accepting connections yet -- retry until the timeout.
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  return false;
}

async function startEmbeddedServer(): Promise<string> {
  const serverPath = standaloneServerPath();
  if (!fs.existsSync(serverPath)) {
    throw new Error(
      `Embedded Next.js server not found at ${serverPath}. Run "npm run electron:build" first.`,
    );
  }

  const port = await findFreePort();
  embeddedServerProcess = spawn(process.execPath, [serverPath], {
    cwd: path.dirname(serverPath),
    env: {
      ...process.env,
      PORT: String(port),
      // "localhost", not "127.0.0.1" -- matches the setWindowOpenHandler /
      // will-navigate origin checks below, which only trust http://localhost.
      HOSTNAME: "localhost",
      NODE_ENV: "production",
      // Runs the packaged Electron binary as a plain Node.js process instead
      // of relaunching Electron itself -- the standard approach for spawning
      // a Node child process from a packaged Electron app with no separate
      // Node.js installation required on the user's machine.
      ELECTRON_RUN_AS_NODE: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  embeddedServerProcess.stdout?.on("data", (chunk: Buffer) => {
    console.log(`[embedded-server] ${chunk.toString().trim()}`);
  });
  embeddedServerProcess.stderr?.on("data", (chunk: Buffer) => {
    console.error(`[embedded-server] ${chunk.toString().trim()}`);
  });
  embeddedServerProcess.on("exit", (code) => {
    console.log(`Embedded Next.js server exited with code ${code}`);
    embeddedServerProcess = null;
  });

  const url = `http://localhost:${port}`;
  const ready = await waitForServerReady(url);
  if (!ready) {
    throw new Error("Embedded Next.js server did not become ready in time.");
  }
  return url;
}

function stopEmbeddedServer(): void {
  if (embeddedServerProcess && !embeddedServerProcess.killed) {
    embeddedServerProcess.kill();
    embeddedServerProcess = null;
  }
}

// ── Backend (Docker) readiness + self-contained auto-start ─────────────────
// Previously this only checked that the `docker` CLI binary was on PATH --
// true even when the application containers aren't running or aren't
// healthy -- and never actually blocked window creation on failure (finding
// #16). It has since grown from "poll and block" into a real auto-start:
// the installer bundles deploy/docker-compose.yaml + docker-compose.
// installer.yaml (the latter swaps every build: context for the matching
// image published to GHCR by .github/workflows/release.yml) plus .env.example,
// so on a machine with just Docker Desktop -- no cloned repo required -- this
// generates a working .env (TLS certs via tls-certs.ts, secrets via
// env-generator.ts, an LLM key via the first-run wizard) and runs
// `docker compose up -d` itself. The manual retry/quit dialog only appears
// if that auto-start attempt itself fails (e.g. Docker Desktop isn't
// installed at all).
async function isBackendReady(): Promise<boolean> {
  try {
    const response = await fetch(GATEWAY_READYZ_URL);
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForBackendReady(timeoutMs: number): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (await isBackendReady()) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 2_000));
  }
  return false;
}

async function isDockerCliAvailable(): Promise<boolean> {
  return new Promise((resolve) => {
    const check = spawn("docker", ["version", "--format", "{{.Server.Version}}"], {
      stdio: "ignore",
    });
    check.on("error", () => resolve(false));
    check.on("exit", (code) => resolve(code === 0));
  });
}

/** Resolves the bundled deploy/ directory: process.resourcesPath/deploy in
 * the packaged app (see package.json build.extraResources), or the repo's
 * own deploy/ directory when running unpackaged (npm run electron:dev). */
function resourcesDeployDir(): string {
  const packaged = path.join(process.resourcesPath, "deploy");
  if (fs.existsSync(packaged)) {
    return packaged;
  }
  return path.join(app.getAppPath(), "..", "..", "deploy");
}

function userDataEnvPath(): string {
  return path.join(app.getPath("userData"), "backend.env");
}

let startingWindow: BrowserWindow | null = null;

function showStartingWindow(): void {
  startingWindow = new BrowserWindow({
    width: 460,
    height: 280,
    resizable: false,
    frame: false,
    backgroundColor: "#0d1117",
    webPreferences: {
      preload: path.join(__dirname, "starting-preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  void startingWindow.loadFile(path.join(__dirname, "starting.html"));
}

function updateStartingStatus(detail: string): void {
  startingWindow?.webContents.send(STARTING_WINDOW_CHANNEL, detail);
}

function closeStartingWindow(): void {
  if (startingWindow && !startingWindow.isDestroyed()) {
    startingWindow.close();
  }
  startingWindow = null;
}

async function runFirstRunWizard(): Promise<LlmProviderKeys> {
  return new Promise((resolve) => {
    const wizardWindow = new BrowserWindow({
      width: 640,
      height: 680,
      resizable: false,
      frame: false,
      backgroundColor: "#0d1117",
      webPreferences: {
        preload: path.join(__dirname, "setup-preload.js"),
        contextIsolation: true,
        nodeIntegration: false,
        sandbox: true,
      },
    });
    void wizardWindow.loadFile(path.join(__dirname, "setup-wizard.html"));

    const cleanup = () => {
      ipcMain.removeListener(SETUP_WIZARD_CHANNELS.SUBMIT, handleSubmit);
      ipcMain.removeListener(SETUP_WIZARD_CHANNELS.QUIT, handleQuit);
    };
    const handleSubmit = (
      _event: unknown,
      keys: { gemini: string; openai: string; anthropic: string },
    ) => {
      cleanup();
      wizardWindow.close();
      resolve({
        gemini: keys.gemini || undefined,
        openai: keys.openai || undefined,
        anthropic: keys.anthropic || undefined,
      });
    };
    const handleQuit = () => {
      cleanup();
      app.quit();
    };
    ipcMain.on(SETUP_WIZARD_CHANNELS.SUBMIT, handleSubmit);
    ipcMain.on(SETUP_WIZARD_CHANNELS.QUIT, handleQuit);
  });
}

/** Returns the path to a ready-to-use .env for the bundled stack, running
 * the first-run wizard (TLS certs + secrets + an LLM key) only if one
 * doesn't already exist from a previous launch. */
async function ensureBackendConfigured(): Promise<string | null> {
  const envPath = userDataEnvPath();
  if (fs.existsSync(envPath)) {
    return envPath;
  }

  const deployDir = resourcesDeployDir();
  const templatePath = path.join(deployDir, "..", ".env.example");
  if (!fs.existsSync(templatePath)) {
    console.error(`Bundled .env.example template not found at ${templatePath}`);
    return null;
  }

  const llmKeys = await runFirstRunWizard();
  ensureTlsCertificates(path.join(deployDir, ".local"));
  generateEnvFile({ templatePath, outputEnvPath: envPath, llmKeys });
  return envPath;
}

/** Runs `docker compose up -d` (no --build) against the bundled compose
 * files, which reference published GHCR images -- never builds from
 * source. Returns true only if the command itself exited 0; readiness is
 * polled separately since containers can take a while to become healthy. */
async function startBackendStack(envPath: string): Promise<boolean> {
  const deployDir = resourcesDeployDir();
  const baseCompose = path.join(deployDir, "docker-compose.yaml");
  const installerCompose = path.join(deployDir, "docker-compose.installer.yaml");
  if (!fs.existsSync(baseCompose) || !fs.existsSync(installerCompose)) {
    console.error(`Bundled compose files not found under ${deployDir}`);
    return false;
  }

  return new Promise((resolve) => {
    const child = spawn(
      "docker",
      [
        "compose",
        "--env-file", envPath,
        "--project-directory", deployDir,
        "-f", baseCompose,
        "-f", installerCompose,
        "up",
        "-d",
      ],
      { cwd: deployDir, stdio: ["ignore", "pipe", "pipe"] },
    );
    child.stdout?.on("data", (chunk: Buffer) => console.log(`[docker-compose] ${chunk.toString().trim()}`));
    child.stderr?.on("data", (chunk: Buffer) => console.error(`[docker-compose] ${chunk.toString().trim()}`));
    child.on("error", (error) => {
      console.error("Failed to spawn docker compose:", error);
      resolve(false);
    });
    child.on("exit", (code) => resolve(code === 0));
  });
}

async function ensureBackendReady(): Promise<boolean> {
  if (await isBackendReady()) {
    return true;
  }

  if (await isDockerCliAvailable()) {
    showStartingWindow();
    try {
      const envPath = await ensureBackendConfigured();
      if (envPath) {
        updateStartingStatus("Pulling images and starting containers (first run can take a few minutes)...");
        const started = await startBackendStack(envPath);
        if (started) {
          updateStartingStatus("Waiting for services to report healthy...");
          const ready = await waitForBackendReady(BACKEND_STARTUP_TIMEOUT_MS);
          if (ready) {
            return true;
          }
        }
      }
    } finally {
      closeStartingWindow();
    }
  }

  // Auto-start failed, or Docker Desktop itself isn't installed -- fall
  // back to the manual retry/quit dialog.
  for (;;) {
    if (await isBackendReady()) {
      return true;
    }
    const { response } = await dialog.showMessageBox({
      type: "error",
      title: "Backend Not Ready",
      message: "theFactory's Docker backend is not reachable yet.",
      detail:
        `Could not reach ${GATEWAY_READYZ_URL}, and automatic startup did not succeed. ` +
        "Make sure Docker Desktop is installed and running, then click Retry.",
      buttons: ["Retry", "Quit"],
      defaultId: 0,
      cancelId: 1,
    });
    if (response === 1) {
      return false;
    }
  }
}


// ── Window creation ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    // 7A — Hide native frame; ElectronTitlebar component draws its own.
    frame: false,
    // Matches --hgr-bg token so there's no flash of white on load.
    backgroundColor: "#0d1117",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,   // Mandatory — prevents prototype-pollution attacks.
      nodeIntegration: false,   // Never enable — direct Node access in renderer is unsafe.
      sandbox: true,            // Renderer can only use contextBridge APIs.
      spellcheck: true,         // 4F — Screen reader / accessibility aid.
      // Disable features not used; reduces attack surface.
      // webgl: false, // Enabled for any future visualizations
      plugins: false,
    },
  });

  // Load the Next.js app — dev server in development, embedded standalone
  // server (spawned as a child process) in the packaged app.
  let appUrl: string;
  try {
    appUrl = isDev ? `http://localhost:${NEXT_DEV_PORT}` : await startEmbeddedServer();
  } catch (error) {
    console.error("Failed to start embedded Next.js server:", error);
    dialog.showErrorBox(
      "Failed to Start Mission Control",
      error instanceof Error ? error.message : "Unknown error starting the embedded server.",
    );
    app.quit();
    return;
  }

  void mainWindow.loadURL(appUrl).catch((error) => {
    console.error(`Failed to load Mission Control UI from ${appUrl}:`, error);
  });

  // Security — keep external URLs out of the app window. Anything that isn't a
  // localhost dev URL or the local file:// bundle opens in the system browser.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith("http://localhost") && !url.startsWith("file://")) {
      if (!isE2E) {
        void shell.openExternal(url);
      }
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith("http://localhost") && !url.startsWith("file://")) {
      event.preventDefault();
      if (!isE2E) {
        void shell.openExternal(url);
      }
    }
  });

  // Open DevTools in dev mode.
  if (isDev) {
    mainWindow.webContents.openDevTools({ mode: "detach" });
  }

  // Mirror window state changes to the renderer (ElectronTitlebar uses this
  // to switch between maximize and restore icons).
  mainWindow.on("maximize", () =>
    mainWindow?.webContents.send(IPC_CHANNELS.WINDOW_STATE_CHANGED, true),
  );
  mainWindow.on("unmaximize", () =>
    mainWindow?.webContents.send(IPC_CHANNELS.WINDOW_STATE_CHANGED, false),
  );

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ── App lifecycle ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  if (!isE2E) {
    const backendReady = await ensureBackendReady();
    if (!backendReady) {
      app.quit();
      return;
    }
  }
  await createWindow();

  // 7B — System tray. Skip in E2E so Playwright can close the app cleanly.
  if (!isE2E) {
    setupTray(mainWindow);
  }

  // 7D — Auto-update.
  setupUpdater();

  // ── IPC: 7A Window controls ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  ipcMain.on(IPC_CHANNELS.WINDOW_MINIMIZE, () => mainWindow?.minimize());

  ipcMain.on(IPC_CHANNELS.WINDOW_MAXIMIZE, () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
  });

  ipcMain.on(IPC_CHANNELS.WINDOW_CLOSE, () => mainWindow?.close());

  ipcMain.handle(IPC_CHANNELS.WINDOW_IS_MAXIMIZED, () => mainWindow?.isMaximized() ?? false);

  // ── IPC: 7B Tray updates ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

  // ── IPC: 7C File system dialogs ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────      
  ipcMain.handle(IPC_CHANNELS.FS_SHOW_OPEN, async (_, options: {
    title?: string;
    properties?: ("openFile" | "openDirectory" | "multiSelections")[];
    filters?: Array<{ name: string; extensions: string[] }>;
  } = {}) => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
      title: options.title ?? "Select repository root",
      properties: options.properties ?? ["openDirectory"],
      filters: options.filters,
    });
    return result.canceled ? null : result.filePaths;
  });

  ipcMain.handle(IPC_CHANNELS.FS_SHOW_SAVE, async (_, options: {
    title?: string;
    defaultPath?: string;
    filters?: Array<{ name: string; extensions: string[] }>;
  } = {}) => {
    if (!mainWindow) return null;
    const result = await dialog.showSaveDialog(mainWindow, options);
    return result.canceled ? null : result.filePath;
  });

  // ── IPC: 7F Shell artifact directory ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
  // Opens the artifact output directory in the system file manager (Finder /
  // Explorer / Nautilus). Path comes from the artifact's storage_path field.
  // If dirPath points to a file (contains a '.'), opens its parent directory.
  // Only called from the Output page when isElectron() is true.
  ipcMain.handle(IPC_CHANNELS.SHELL_OPEN_ARTIFACT_DIR, async (_, dirPath: string) => {
    if (!dirPath || typeof dirPath !== "string") return;
    const target = path.basename(dirPath).includes(".") ? path.dirname(dirPath) : dirPath;
    await shell.openPath(target);
  });

  // ── IPC: 7E App info ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  ipcMain.handle(IPC_CHANNELS.APP_PLATFORM, () => process.platform);

  // ── IPC: A9 Offline diagnostics bundle ───────────────────────────────────────────────────────────────────────────────────────────────────────────
  // Generates the standard local diagnostics folder; returns its path. Offline,
  // secret-free, never uploaded.
  ipcMain.handle(IPC_CHANNELS.DIAGNOSTICS_GENERATE, () => generateDiagnostics());
});

// macOS: re-open window when dock icon is clicked and no windows are open.
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    void createWindow();
  }
});

// Windows / Linux: quit when all windows close.
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

// Stop our own embedded Next.js server child process on quit. Per product
// decision, this does NOT touch the separate Docker Compose backend --
// quitting Electron leaves it running so in-flight missions aren't
// interrupted; the operator stops it explicitly (stop_app.bat / make down).
app.on("before-quit", () => {
  stopEmbeddedServer();
});
