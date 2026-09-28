import { spawn, type ChildProcess } from "child_process";
import fs from "fs";
import { createServer } from "net";
import path from "path";
import { app, BrowserWindow, dialog, ipcMain, Notification, shell } from "electron";
import { setupTray, type TrayController } from "./tray";
import { setupUpdater } from "./updater";  // version IPC only — auto-update disabled
import { installCrashHandlers, generateDiagnostics } from "./diagnostics";
import { IPC_CHANNELS } from "../app/lib/electron-bridge";
import { ensureTlsCertificates } from "./tls-certs";
import { generateEnvFile, upsertEnvValues, type LlmProviderKeys } from "./env-generator";
import {
  SETUP_WIZARD_CHANNELS,
  STARTING_WINDOW_ACTIONS,
  STARTING_WINDOW_CHANNEL,
} from "./wizard-ipc-channels";
import {
  STARTUP_STEPS,
  imageTagForVersion,
  imagesToPull,
  overallProgress,
  standaloneServerCandidates,
  embeddedServerEnv,
  gatewayBaseUrl,
  parseEnvText,
  sandboxRetags,
  stackCommands,
  type StackPaths,
  type StartupStepId,
} from "./factory-stack";
import type { StatusUpdate } from "./starting-preload";

/**
 * Product name, and therefore the user-data folder. Electron otherwise names
 * the folder after package.json "name" (mission-control), which is not where
 * the docs point operators for logs, nor where the uninstaller's "Remove
 * everything" deletes app data ($APPDATA\${PRODUCT_NAME} in installer.nsh).
 * Must run before anything calls app.getPath("userData").
 */
export const PRODUCT_NAME = "theFactory Mission Control";
app.setName(PRODUCT_NAME);
app.setPath("userData", path.join(app.getPath("appData"), PRODUCT_NAME));

// A8 — install application-boundary crash handlers before anything else can throw.
installCrashHandlers();

const isDev = process.env.ELECTRON_DEV === "1";
const isE2E = process.env.ELECTRON_E2E === "1";
/** Launched by "Start with Windows": come up in the tray, no window. */
const startHidden = process.argv.includes("--hidden");
const NEXT_DEV_PORT = 3100; // Match next dev --port in package.json
const GATEWAY_READYZ_URL =
  process.env.MISSION_CONTROL_GATEWAY_READYZ_URL?.trim() || "http://localhost:8100/readyz";
// A first start downloads ~14 images; give services this long to turn healthy
// once they are running before offering the manual retry/quit dialog.
const BACKEND_STARTUP_TIMEOUT_MS = 20 * 60 * 1000;
const HEALTH_POLL_MS = 15_000;
/**
 * Registry value name for "Start with Windows". Must match the value the NSIS
 * finish page writes (build/installer.nsh) and the appId electron-builder uses
 * as the AppUserModelID, so the app and the installer see one setting.
 */
const AUTOSTART_NAME = "com.holygrail.mission-control";
const DOCKER_DESKTOP_URL = "https://docs.docker.com/desktop/setup/install/windows-install/";

let mainWindow: BrowserWindow | null = null;
let statusWindow: BrowserWindow | null = null;
let embeddedServerProcess: ChildProcess | null = null;
let tray: TrayController | null = null;
let isQuitting = false;
let trayHintShown = false;
let lastStatus: StatusUpdate = {};

// Second launch (desktop shortcut while already in the tray): surface the
// running instance instead of starting a second copy of everything.
if (!isE2E && !app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => showMainWindow());
}

// ── Logging ─────────────────────────────────────────────────────────────────
function logsDir(): string {
  const dir = path.join(app.getPath("userData"), "Logs");
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function logLine(line: string): void {
  const stamped = `${new Date().toISOString()} ${line}`;
  console.log(stamped);
  try {
    fs.appendFileSync(path.join(logsDir(), "factory.log"), stamped + "\n", "utf-8");
  } catch {
    // Logging must never break startup.
  }
}

function openLogs(): void {
  void shell.openPath(logsDir());
}

// ── Embedded standalone Next.js server (packaged/production only) ──────────
// Electron previously loaded a static export (`out/index.html`), which
// physically cannot serve any of this app's app/api/* routes (vault, session,
// gateway proxy, repo import, etc.) -- see
// docs/FULL_APP_REMEDIATION_PLAN_2026-07-05.md §7.1. This spawns the same
// `output: "standalone"` Next.js server the build produces (see
// scripts/build-electron.mjs) as a child process on a free local port and
// loads that instead.

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
  const candidates = standaloneServerCandidates(app.getAppPath(), process.cwd());
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
      ...embeddedServerConfig(),
      PORT: String(port),
      // "localhost", not "127.0.0.1" -- matches the setWindowOpenHandler /
      // will-navigate origin checks below, which only trust http://localhost.
      HOSTNAME: "localhost",
      NODE_ENV: "production",
      // Runs the packaged Electron binary as a plain Node.js process -- no
      // separate Node.js installation required on the user's machine.
      ELECTRON_RUN_AS_NODE: "1",
    },
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  embeddedServerProcess.stdout?.on("data", (chunk: Buffer) => {
    console.log(`[embedded-server] ${chunk.toString().trim()}`);
  });
  embeddedServerProcess.stderr?.on("data", (chunk: Buffer) => {
    console.error(`[embedded-server] ${chunk.toString().trim()}`);
  });
  const spawnFailure = new Promise<Error>((resolve) => {
    embeddedServerProcess?.once("error", (error) => {
      console.error("Embedded Next.js server failed to start:", error);
      resolve(error);
    });
  });
  embeddedServerProcess.on("exit", (code) => {
    console.log(`Embedded Next.js server exited with code ${code}`);
    embeddedServerProcess = null;
  });

  const url = `http://localhost:${port}`;
  const outcome = await Promise.race([
    waitForServerReady(url),
    spawnFailure,
  ]);
  if (outcome instanceof Error) {
    throw new Error(`Mission Control's built-in server could not start (${outcome.message}).`);
  }
  if (!outcome) {
    throw new Error("Embedded Next.js server did not become ready in time.");
  }
  return url;
}

/** The installed stack's settings for the embedded server; {} when not configured. */
function embeddedServerConfig(): Record<string, string> {
  const envPath = path.join(app.getPath("userData"), "backend.env");
  if (!fs.existsSync(envPath)) return {};
  const vaultDir = path.join(app.getPath("userData"), "vault");
  fs.mkdirSync(vaultDir, { recursive: true });
  return embeddedServerEnv(parseEnvText(fs.readFileSync(envPath, "utf-8")), path.join(vaultDir, "vault.json"));
}

function stopEmbeddedServer(): void {
  if (embeddedServerProcess && !embeddedServerProcess.killed) {
    embeddedServerProcess.kill();
    embeddedServerProcess = null;
  }
}

// ── Status / progress window ───────────────────────────────────────────────
function showStatusWindow(): void {
  if (statusWindow && !statusWindow.isDestroyed()) {
    statusWindow.show();
    statusWindow.focus();
    return;
  }
  statusWindow = new BrowserWindow({
    width: 560,
    height: 520,
    resizable: false,
    frame: false,
    title: "theFactory — Status",
    backgroundColor: "#0d1117",
    webPreferences: {
      preload: path.join(__dirname, "starting-preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  void statusWindow.loadFile(path.join(__dirname, "starting.html"));
  statusWindow.webContents.once("did-finish-load", () => {
    // Replay the latest state so a window reopened from the tray is current.
    statusWindow?.webContents.send(STARTING_WINDOW_CHANNEL, { ...lastStatus, steps: STARTUP_STEPS });
  });
  statusWindow.on("closed", () => {
    statusWindow = null;
  });
}

function hideStatusWindow(): void {
  if (statusWindow && !statusWindow.isDestroyed()) {
    statusWindow.close();
  }
  statusWindow = null;
}

function report(update: StatusUpdate): void {
  if (update.log) logLine(update.log);
  lastStatus = { ...lastStatus, ...update, log: undefined };
  statusWindow?.webContents.send(STARTING_WINDOW_CHANNEL, { ...update, steps: STARTUP_STEPS });
}

function stepReport(step: StartupStepId, detail: string, fraction = 0, log?: string): void {
  report({ step, detail, progress: overallProgress(step, fraction), log: log ?? detail, failed: false });
}

// ── Docker helpers ─────────────────────────────────────────────────────────
type RunResult = { code: number | null; output: string };

/** Runs `docker <args>`, streaming each output line to the status log. */
function runDocker(args: string[], onLine?: (line: string) => void): Promise<RunResult> {
  return new Promise((resolve) => {
    const child = spawn("docker", args, { stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
    let output = "";
    const consume = (chunk: Buffer) => {
      const text = chunk.toString();
      output += text;
      for (const line of text.split(/\r?\n/)) {
        if (line.trim()) onLine?.(line.trim());
      }
    };
    child.stdout?.on("data", consume);
    child.stderr?.on("data", consume);
    child.on("error", (error) => resolve({ code: null, output: String(error) }));
    child.on("exit", (code) => resolve({ code, output }));
  });
}

type DockerState = "ready" | "not-running" | "missing";

async function dockerState(): Promise<DockerState> {
  const result = await runDocker(["version", "--format", "{{.Server.Version}}"]);
  if (result.code === 0) return "ready";
  return result.code === null ? "missing" : "not-running";
}

/** Operator decision: check and guide -- never install third-party software silently. */
async function ensureDockerReady(): Promise<boolean> {
  for (;;) {
    stepReport("docker", "Checking Docker Desktop…");
    const state = await dockerState();
    if (state === "ready") {
      stepReport("docker", "Docker Desktop is running.", 1);
      return true;
    }
    const missing = state === "missing";
    report({
      step: "docker",
      failed: true,
      detail: missing ? "Docker Desktop is not installed." : "Docker Desktop is not running.",
      log: missing ? "docker CLI not found on PATH" : "docker daemon did not answer",
    });
    const { response } = await dialog.showMessageBox({
      type: "warning",
      title: "Docker Desktop required",
      message: missing
        ? "theFactory runs on Docker Desktop, which is not installed."
        : "Docker Desktop is installed but not running.",
      detail: missing
        ? "Install Docker Desktop (with the WSL 2 backend), start it, then click Retry. " +
          "theFactory never installs third-party software for you."
        : "Start Docker Desktop and wait until it says it is running, then click Retry.",
      buttons: missing ? ["Get Docker Desktop", "Retry", "Quit"] : ["Retry", "Quit"],
      defaultId: missing ? 0 : 0,
      cancelId: missing ? 2 : 1,
      noLink: true,
    });
    if (missing && response === 0) {
      void shell.openExternal(DOCKER_DESKTOP_URL);
      continue;
    }
    if ((missing && response === 2) || (!missing && response === 1)) {
      return false;
    }
  }
}

// ── Backend configuration ──────────────────────────────────────────────────
/** process.resourcesPath/deploy in the packaged app, or the repo's deploy/ unpackaged. */
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

function stackPaths(): StackPaths {
  return { deployDir: resourcesDeployDir(), envPath: userDataEnvPath() };
}

function imageTag(): string {
  return imageTagForVersion(app.getVersion());
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
      isQuitting = true;
      app.quit();
    };
    ipcMain.on(SETUP_WIZARD_CHANNELS.SUBMIT, handleSubmit);
    ipcMain.on(SETUP_WIZARD_CHANNELS.QUIT, handleQuit);
  });
}

/**
 * Returns a ready-to-use backend .env, running the first-run wizard only when
 * none exists. Values that must track the INSTALLED app, not the day of first
 * install, are refreshed on every start: the image tag (an upgraded app runs
 * the images released with it), the sandbox workspace path, and the TLS certs
 * (they live under the install directory, which an upgrade replaces).
 */
async function ensureBackendConfigured(): Promise<string | null> {
  const { deployDir, envPath } = stackPaths();
  if (!fs.existsSync(envPath)) {
    const templatePath = path.join(deployDir, "..", ".env.example");
    if (!fs.existsSync(templatePath)) {
      report({ step: "configure", failed: true, detail: "Bundled configuration template is missing.",
        log: `.env.example not found at ${templatePath}` });
      return null;
    }
    stepReport("configure", "First run: choose an AI provider key…");
    hideStatusWindow();
    const llmKeys = await runFirstRunWizard();
    showStatusWindow();
    generateEnvFile({ templatePath, outputEnvPath: envPath, llmKeys });
    stepReport("configure", "Generated a private configuration with fresh secrets.", 0.5);
  }

  ensureTlsCertificates(path.join(deployDir, ".local"));
  const sandboxWorkspace = path.join(app.getPath("userData"), "sandbox-workspace");
  fs.mkdirSync(sandboxWorkspace, { recursive: true });
  upsertEnvValues(envPath, {
    FACTORY_IMAGE_TAG: imageTag(),
    // Runtime QC mounts per-run workspaces from here into the sandbox; it
    // must be a host path Docker Desktop can bind-mount.
    SANDBOX_WORKSPACE_HOST_ROOT: sandboxWorkspace,
    COMPOSE_PROJECT_DIR: deployDir,
  });
  stepReport("configure", "Configuration ready.", 1);
  return envPath;
}

/** Pulls each factory image not already present, counting them for the progress bar. */
async function ensureImages(): Promise<boolean> {
  const tag = imageTag();
  const images = imagesToPull(tag);
  for (const [index, image] of images.entries()) {
    const fraction = index / images.length;
    const present = await runDocker(["image", "inspect", "--format", "{{.Id}}", image]);
    if (present.code === 0) {
      stepReport("images", `Image ${index + 1} of ${images.length} already present.`, fraction,
        `present: ${image}`);
      continue;
    }
    stepReport("images", `Downloading image ${index + 1} of ${images.length}…`, fraction,
      `pulling ${image}`);
    const pulled = await runDocker(["pull", image], (line) => {
      // Docker's per-layer progress is noisy; keep only milestone lines.
      if (/Pull complete|Downloaded newer|Status:|digest:|error/i.test(line)) {
        report({ log: line });
      }
    });
    if (pulled.code !== 0) {
      report({ step: "images", failed: true, detail: `Could not download ${image}.`,
        log: pulled.output.trim().split("\n").slice(-3).join(" | ") });
      return false;
    }
  }
  for (const [source, local] of sandboxRetags(tag)) {
    await runDocker(["tag", source, local]);
  }
  stepReport("images", `All ${images.length} images ready.`, 1);
  return true;
}

function gatewayReadyzUrl(): string {
  if (process.env.MISSION_CONTROL_GATEWAY_READYZ_URL?.trim()) return GATEWAY_READYZ_URL;
  const envPath = userDataEnvPath();
  if (!fs.existsSync(envPath)) return GATEWAY_READYZ_URL;
  return `${gatewayBaseUrl(parseEnvText(fs.readFileSync(envPath, "utf-8")))}/readyz`;
}

async function isBackendReady(): Promise<boolean> {
  try {
    const response = await fetch(gatewayReadyzUrl());
    return response.ok;
  } catch {
    return false;
  }
}

async function startFactoryStack(): Promise<boolean> {
  for (const argv of stackCommands("up", stackPaths(), imageTag())) {
    stepReport("start", "Starting services…", 0.2, "docker compose up");
    const result = await runDocker(argv, (line) => report({ log: line }));
    if (result.code !== 0) {
      report({ step: "start", failed: true, detail: "Services failed to start. See the log below." });
      return false;
    }
  }
  stepReport("start", "Services started.", 1);
  const start = Date.now();
  while (Date.now() - start < BACKEND_STARTUP_TIMEOUT_MS) {
    if (await isBackendReady()) {
      report({ step: "health", detail: "theFactory is ready.", progress: 100, log: "backend ready" });
      return true;
    }
    const waited = (Date.now() - start) / BACKEND_STARTUP_TIMEOUT_MS;
    stepReport("health", "Waiting for services to report healthy…", Math.min(0.95, waited * 4));
    await new Promise((resolve) => setTimeout(resolve, 3_000));
  }
  report({ step: "health", failed: true, detail: "Services did not become healthy in time." });
  return false;
}

/** Brings the backend up, showing the status window while it does. */
async function ensureBackendReady(options: { interactive: boolean }): Promise<boolean> {
  if (await isBackendReady()) {
    tray?.setHealth("running");
    return true;
  }
  if (!app.isPackaged) {
    // A developer checkout runs its own stack (make up); the packaged images
    // for this version do not exist yet.
    await dialog.showMessageBox({
      type: "info",
      title: "Backend not running",
      message: "Start the development stack with `make up`, then relaunch.",
    });
    return false;
  }

  tray?.setBusy("Factory starting…");
  if (options.interactive) showStatusWindow();
  lastStatus = {};
  report({ title: "Starting theFactory", steps: STARTUP_STEPS, progress: 0 });
  try {
    if (!(await ensureDockerReady())) return false;
    if (!(await ensureBackendConfigured())) return false;
    if (!(await ensureImages())) return false;
    if (!(await startFactoryStack())) return false;
    tray?.setHealth("running");
    return true;
  } finally {
    tray?.setBusy(null);
  }
}

async function stopFactory(): Promise<void> {
  tray?.setBusy("Stopping factory…");
  logLine("stopping factory (containers kept, data kept)");
  for (const argv of stackCommands("stop", stackPaths(), imageTag())) {
    await runDocker(argv, (line) => logLine(line));
  }
  tray?.setBusy(null);
  tray?.setHealth("stopped");
}

async function pollHealth(): Promise<void> {
  if (!tray) return;
  if (await isBackendReady()) {
    tray.setHealth("running");
    return;
  }
  const state = await dockerState();
  tray.setHealth(state === "ready" ? "stopped" : "unreachable");
}

// ── Start with Windows (opt-in, off by default) ────────────────────────────
function loginItemQuery() {
  return { path: process.execPath, args: ["--hidden"], name: AUTOSTART_NAME };
}

function isAutoStartEnabled(): boolean {
  if (process.platform !== "win32" || !app.isPackaged) return false;
  return app.getLoginItemSettings(loginItemQuery()).openAtLogin;
}

function setAutoStart(enabled: boolean): void {
  if (process.platform !== "win32" || !app.isPackaged) return;
  app.setLoginItemSettings({ ...loginItemQuery(), openAtLogin: enabled });
  logLine(`start with Windows ${enabled ? "enabled" : "disabled"}`);
  tray?.refresh();
}

// ── Window creation ─────────────────────────────────────────────────────────
function showMainWindow(route?: string): void {
  if (!mainWindow) {
    void createWindow().then(() => showMainWindow(route));
    return;
  }
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
  if (route) mainWindow.webContents.send("navigate", route);
}

async function createWindow(): Promise<void> {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    show: false,
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
      plugins: false,
    },
  });

  let appUrl: string;
  try {
    appUrl = isDev ? `http://localhost:${NEXT_DEV_PORT}` : await startEmbeddedServer();
  } catch (error) {
    console.error("Failed to start embedded Next.js server:", error);
    dialog.showErrorBox(
      "Failed to Start Mission Control",
      error instanceof Error ? error.message : "Unknown error starting the embedded server.",
    );
    isQuitting = true;
    app.quit();
    return;
  }

  mainWindow.once("ready-to-show", () => {
    if (!startHidden) mainWindow?.show();
  });
  void mainWindow.loadURL(appUrl).catch((error) => {
    console.error(`Failed to load Mission Control UI from ${appUrl}:`, error);
  });

  // Security — keep external URLs out of the app window.
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

  if (isDev) {
    mainWindow.webContents.openDevTools({ mode: "detach" });
  }

  mainWindow.on("maximize", () =>
    mainWindow?.webContents.send(IPC_CHANNELS.WINDOW_STATE_CHANGED, true),
  );
  mainWindow.on("unmaximize", () =>
    mainWindow?.webContents.send(IPC_CHANNELS.WINDOW_STATE_CHANGED, false),
  );

  // Operator decision (2026-09-27): closing the window keeps theFactory
  // running in the tray. Only an explicit quit ends the app.
  mainWindow.on("close", (event) => {
    if (isQuitting || isE2E || !tray) return;
    event.preventDefault();
    mainWindow?.hide();
    if (!trayHintShown && Notification.isSupported()) {
      trayHintShown = true;
      new Notification({
        title: "theFactory is still running",
        body: "Missions keep running. Use the tray icon to reopen, stop the factory, or quit.",
      }).show();
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

// ── App lifecycle ───────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  if (!isE2E) {
    tray = setupTray({
      showWindow: (route) => showMainWindow(route),
      showStatus: () => showStatusWindow(),
      openLogs,
      startFactory: () => {
        void ensureBackendReady({ interactive: true }).then((ok) => {
          if (ok) hideStatusWindow();
        });
      },
      stopFactory: () => void stopFactory(),
      isAutoStartEnabled,
      setAutoStart,
      quit: () => {
        isQuitting = true;
        app.quit();
      },
      quitAndStop: () => {
        void stopFactory().finally(() => {
          isQuitting = true;
          app.quit();
        });
      },
    });
    const backendReady = await ensureBackendReady({ interactive: !startHidden });
    if (!backendReady && !startHidden) {
      const { response } = await dialog.showMessageBox({
        type: "error",
        title: "theFactory could not start",
        message: "The factory backend did not start.",
        detail: "The status window and the logs folder show what happened. You can retry from the tray.",
        buttons: ["Open logs folder", "Keep in tray", "Quit"],
        defaultId: 1,
        cancelId: 2,
        noLink: true,
      });
      if (response === 0) openLogs();
      if (response === 2) {
        isQuitting = true;
        app.quit();
        return;
      }
    } else {
      hideStatusWindow();
    }
    setInterval(() => void pollHealth(), HEALTH_POLL_MS);
  }
  await createWindow();

  setupUpdater();

  ipcMain.on(STARTING_WINDOW_ACTIONS.OPEN_LOGS, () => openLogs());
  ipcMain.on(STARTING_WINDOW_ACTIONS.HIDE, () => statusWindow?.hide());

  // ── IPC: 7A Window controls ──────────────────────────────────────────────
  ipcMain.on(IPC_CHANNELS.WINDOW_MINIMIZE, () => mainWindow?.minimize());

  ipcMain.on(IPC_CHANNELS.WINDOW_MAXIMIZE, () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
  });

  // The titlebar's close button follows the same rule as the window's own:
  // hide to tray, don't quit.
  ipcMain.on(IPC_CHANNELS.WINDOW_CLOSE, () => mainWindow?.close());

  ipcMain.handle(IPC_CHANNELS.WINDOW_IS_MAXIMIZED, () => mainWindow?.isMaximized() ?? false);

  // ── IPC: 7C File system dialogs ─────────────────────────────────────────
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

  // ── IPC: 7F Shell artifact directory ────────────────────────────────────
  ipcMain.handle(IPC_CHANNELS.SHELL_OPEN_ARTIFACT_DIR, async (_, dirPath: string) => {
    if (!dirPath || typeof dirPath !== "string") return;
    const target = path.basename(dirPath).includes(".") ? path.dirname(dirPath) : dirPath;
    await shell.openPath(target);
  });

  // ── IPC: 7E App info ────────────────────────────────────────────────────
  ipcMain.handle(IPC_CHANNELS.APP_PLATFORM, () => process.platform);

  // ── IPC: A9 Offline diagnostics bundle ──────────────────────────────────
  ipcMain.handle(IPC_CHANNELS.DIAGNOSTICS_GENERATE, () => generateDiagnostics());
});

// macOS: re-open window when dock icon is clicked and no windows are open.
app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    void createWindow();
  }
});

// The tray keeps the app alive with no windows open; without a tray (E2E),
// closing the last window quits as before.
app.on("window-all-closed", () => {
  if (!tray && process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  isQuitting = true;
  stopEmbeddedServer();
  tray?.destroy();
});

