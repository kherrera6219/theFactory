import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import { pathToFileURL } from "url";
import { app, BrowserWindow, dialog, ipcMain, shell } from "electron";
import { setupTray } from "./tray";
import { setupUpdater } from "./updater";  // version IPC only — auto-update disabled
import { installCrashHandlers, generateDiagnostics } from "./diagnostics";
import { IPC_CHANNELS } from "../app/lib/electron-bridge";

// A8 — install application-boundary crash handlers before anything else can throw.
installCrashHandlers();

const isDev = process.env.ELECTRON_DEV === "1";
const isE2E = process.env.ELECTRON_E2E === "1";
const NEXT_DEV_PORT = 3100; // Match next dev --port in package.json

let mainWindow: BrowserWindow | null = null;
function checkDockerAvailability(): { available: boolean; error?: string } {
  try {
    execSync("docker version", { stdio: "ignore" });
    return { available: true };
  } catch (err: any) {
    return { 
      available: false, 
      error: "Docker Desktop or Docker Engine was not found on this system. theFactory backend requires Docker to operate." 
    };
  }
}

function exportedAppUrl(): string {
  const candidates = [
    path.join(app.getAppPath(), "out", "index.html"),
    path.join(process.cwd(), "out", "index.html"),
    path.join(__dirname, "..", "..", "..", "out", "index.html"),
  ];
  const indexPath = candidates.find((candidate) => fs.existsSync(candidate)) ?? candidates[0];
  return pathToFileURL(indexPath).toString();
}


// ── Window creation ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

function createWindow(): void {
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

  // Load the Next.js app — dev server in development, static export in production.
  const appUrl = isDev ? `http://localhost:${NEXT_DEV_PORT}` : exportedAppUrl();

  void mainWindow.loadURL(appUrl).catch((error) => {
    console.error(`Failed to load Mission Control UI from ${appUrl}:`, error);
  });

  // Security — keep external URLs out of the app window. Anything that isn't a
  // localhost dev URL or the local file:// bundle opens in the system browser.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith("http://localhost") && !url.startsWith("file://")) {
      void shell.openExternal(url);
      return { action: "deny" };
    }
    return { action: "allow" };
  });

  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith("http://localhost") && !url.startsWith("file://")) {
      event.preventDefault();
      void shell.openExternal(url);
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

app.whenReady().then(() => {
  if (!isE2E) {
    const docker = checkDockerAvailability();
    if (!docker.available) {
      dialog.showErrorBox("Infrastructure Missing", docker.error!);
    }
  }
  createWindow();

  // 7B — System tray.
  setupTray(mainWindow);

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
    createWindow();
  }
});

// Windows / Linux: quit when all windows close.
app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
