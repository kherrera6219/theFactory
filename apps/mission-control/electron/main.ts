import { execSync } from "child_process";
import path from "path";
import { app, BrowserWindow, dialog, ipcMain } from "electron";
import { setupTray } from "./tray";
import { setupUpdater } from "./updater";
import { IPC_CHANNELS } from "../app/lib/electron-bridge";

const isDev = process.env.ELECTRON_DEV === "1";
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


// â”€â”€ Window creation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 640,
    // 7A â€” Hide native frame; ElectronTitlebar component draws its own.
    frame: false,
    // Matches --hgr-bg token so there's no flash of white on load.
    backgroundColor: "#0d1117",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,   // Mandatory â€” prevents prototype-pollution attacks.
      nodeIntegration: false,   // Never enable â€” direct Node access in renderer is unsafe.
      sandbox: true,            // Renderer can only use contextBridge APIs.
      spellcheck: true,         // 4F â€” Screen reader / accessibility aid.
      // Disable features not used; reduces attack surface.
      // webgl: false, // Enabled for any future visualizations
      plugins: false,
    },
  });

  // Load the Next.js app â€” dev server in development, static export in production.
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

// â”€â”€ App lifecycle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

app.whenReady().then(() => {
  const docker = checkDockerAvailability();
  if (!docker.available) {
    dialog.showErrorBox("Infrastructure Missing", docker.error!);
  }
  createWindow();

  // 7B â€” System tray.
  setupTray(mainWindow);

  // 7D â€” Auto-update.
  setupUpdater(mainWindow);

  // â”€â”€ IPC: 7A Window controls â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

  // â”€â”€ IPC: 7B Tray updates â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  // â”€â”€ IPC: 7C File system dialogs â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€      
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

  // â”€â”€ IPC: 7E App info â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
