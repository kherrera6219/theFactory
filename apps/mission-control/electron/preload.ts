/**
 * 7E — Electron preload script.
 *
 * Runs in the renderer process before page load but has access to Node.js APIs.
 * contextBridge.exposeInMainWorld is the ONLY safe way to share functionality
 * with the renderer when contextIsolation:true (which is mandatory for security).
 *
 * The shape exposed here MUST match the `Window["electronAPI"]` declaration in
 * `app/lib/electron-bridge.ts`. Any mismatch causes silent TypeScript errors in
 * the renderer.
 *
 * Build: tsc --project electron/tsconfig.json → dist/electron/preload.js
 * Referenced as: webPreferences.preload = path.join(__dirname, "preload.js")
 */

import { contextBridge, ipcRenderer } from "electron";
import { IPC_CHANNELS } from "../app/lib/electron-bridge";

contextBridge.exposeInMainWorld("electronAPI", {

  // ── 7A: Window controls ────────────────────────────────────────────────
  minimizeWindow: () =>
    ipcRenderer.send(IPC_CHANNELS.WINDOW_MINIMIZE),

  maximizeWindow: () =>
    ipcRenderer.send(IPC_CHANNELS.WINDOW_MAXIMIZE),

  closeWindow: () =>
    ipcRenderer.send(IPC_CHANNELS.WINDOW_CLOSE),

  isMaximized: (): Promise<boolean> =>
    ipcRenderer.invoke(IPC_CHANNELS.WINDOW_IS_MAXIMIZED),

  onWindowStateChange: (cb: (maximized: boolean) => void): (() => void) => {
    const handler = (_: unknown, maximized: boolean) => cb(maximized);
    ipcRenderer.on(IPC_CHANNELS.WINDOW_STATE_CHANGED, handler);
    return () => ipcRenderer.removeListener(IPC_CHANNELS.WINDOW_STATE_CHANGED, handler);
  },

  // ── 7B: System tray ───────────────────────────────────────────────────
  updateTray: (payload: { activeMissions: number; status: "live" | "offline" }) =>
    ipcRenderer.send(IPC_CHANNELS.TRAY_UPDATE, payload),

  // ── 7C: File system dialogs ───────────────────────────────────────────
  showOpenDialog: (options: object): Promise<string[] | null> =>
    ipcRenderer.invoke(IPC_CHANNELS.FS_SHOW_OPEN, options),

  showSaveDialog: (options: object): Promise<string | null> =>
    ipcRenderer.invoke(IPC_CHANNELS.FS_SHOW_SAVE, options),

  // ── 7D: App version (auto-update disabled; manual installer updates only) ─
  getAppVersion: (): Promise<string> =>
    ipcRenderer.invoke(IPC_CHANNELS.UPDATER_GET_VERSION),

  // ── 7F: Shell — open artifact directory ─────────────────────────────────
  openArtifactDir: (dirPath: string): Promise<void> =>
    ipcRenderer.invoke(IPC_CHANNELS.SHELL_OPEN_ARTIFACT_DIR, dirPath),

  // ── Misc ──────────────────────────────────────────────────────────────
  getPlatform: (): Promise<"darwin" | "win32" | "linux"> =>
    ipcRenderer.invoke(IPC_CHANNELS.APP_PLATFORM),

  // ── A9: Offline diagnostics bundle ──────────────────────────────────────
  generateDiagnostics: (): Promise<string> =>
    ipcRenderer.invoke(IPC_CHANNELS.DIAGNOSTICS_GENERATE),
});
