/**
 * 7E — Electron main process entry point.
 *
 * Start: electron .  (after tsc --project electron/tsconfig.json)
 * Dev:   ELECTRON_DEV=1 electron .
 *
 * Prerequisites:
 *   npm install --save-dev electron electron-builder
 *   npm install --save electron-updater
 *
 * Build chain:
 *   1. next build && next export → out/  (static HTML/CSS/JS)
 *   2. tsc --project electron/tsconfig.json → dist/electron/
 *   3. electron-builder → dist/installers/
 *
 * See electron-builder docs for platform-specific configuration.
 */

import path from "path";
import { app, BrowserWindow, dialog, ipcMain } from "electron";
import { setupTray } from "./tray";
import { setupUpdater } from "./updater";
import { IPC_CHANNELS } from "../app/lib/electron-bridge";

const isDev = process.env.ELECTRON_DEV === "1";
const NEXT_DEV_PORT = 3100; // Match next dev --port in package.json

let mainWindow: BrowserWindow | null = null;

// ── Window creation ───────────────────────────────────────────────────────────

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    // 7A — Hide native frame; ElectronTitlebar component draws its own.
    frame: false,
    // 4F — Screen reader accessible window title.
    accessibleTitle: "Mission Control — HolyGrail Refinery",
    // Matches --hgr-bg token so there's no flash of white on load.
    backgroundColor: "#0d1117",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,   // Mandatory — prevents prototype-pollution attacks.
      nodeIntegration: false,   // Never enable — direct Node access in renderer is unsafe.
      sandbox: true,            // Renderer can only use contextBridge APIs.
      spellcheck: true,         // 4F — Screen reader / accessibility aid.
      // Disable features not used; reduces attack surface.
      webgl: false,
      plugins: false,
    },
  });

  // Load the Next.js app — dev server in development, static export in production.
  const appUrl = isDev
    ? `http://localhost:${NEXT_DEV_PORT}`
    : `file://${path.join(__dirname, "../out/index.html")}`;

  void mainWindow.loadURL(appUrl);

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

// ── App lifecycle ─────────────────────────────────────────────────────────────

app.whenReady().then(() => {
  createWindow();

  // 7B — System tray.
  setupTray(mainWindow);

  // 7D — Auto-update.
  setupUpdater(mainWindow);

  // ── IPC: 7A Window controls ─────────────────────────────────────────────
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

  // ── IPC: 7B Tray updates ────────────────────────────────────────────────
  // The tray object is returned by setupTray() — status bar calls this every
  // 15 s with active mission count and online/offline status.
  // The tray reference is held inside setupTray; future enhancement can store it
  // here to allow dynamic tooltip changes without rebuilding the context menu.

  // ── IPC: 7C File system dialogs ────────────────────────────────────────
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

  // ── IPC: 7E App info ────────────────────────────────────────────────────
  ipcMain.handle(IPC_CHANNELS.APP_PLATFORM, () => process.platform);
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
