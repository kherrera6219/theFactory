/**
 * 7E — Electron IPC bridge (renderer side).
 *
 * All renderer → main communication goes through this module. When the app
 * runs in a plain browser (no Electron), every exported function is a safe
 * no-op that returns `null` or `undefined`.
 *
 * The actual `window.electronAPI` object is injected by `electron/preload.ts`
 * via Electron's contextBridge. This file only uses browser globals — it does
 * NOT import from the `electron` package and is safe inside the Next.js build.
 *
 * IPC channel names are documented here as the authoritative list.
 * Mirror any changes in `electron/preload.ts` and `electron/main.ts`.
 */

// ── IPC channel constants ───────────────────────────────────────────────────
// Kept here so renderer code and the electron/ files share one source of truth.
export const IPC_CHANNELS = {
  // 7A — Window controls
  WINDOW_MINIMIZE: "window:minimize",
  WINDOW_MAXIMIZE: "window:maximize",
  WINDOW_CLOSE: "window:close",
  WINDOW_IS_MAXIMIZED: "window:is-maximized",
  WINDOW_STATE_CHANGED: "window:state-changed",

  // 7B — System tray
  TRAY_UPDATE: "tray:update",

  // 7C — File system dialogs
  FS_SHOW_OPEN: "fs:show-open-dialog",
  FS_SHOW_SAVE: "fs:show-save-dialog",

  // 7D — App version (auto-update disabled)
  UPDATER_GET_VERSION: "updater:get-version",

  // Misc
  APP_PLATFORM: "app:platform",
} as const;

// ── Type declaration for contextBridge API ──────────────────────────────────
// `electron/preload.ts` exposes exactly this shape via contextBridge.
declare global {
  interface Window {
    electronAPI?: {
      // 7A — Window controls
      minimizeWindow(): void;
      maximizeWindow(): void;
      closeWindow(): void;
      isMaximized(): Promise<boolean>;
      /** Returns a cleanup function that removes the listener. */
      onWindowStateChange(cb: (maximized: boolean) => void): () => void;

      // 7B — System tray
      updateTray(payload: { activeMissions: number; status: "live" | "offline" }): void;

      // 7C — File system
      showOpenDialog(options: {
        title?: string;
        properties?: ("openFile" | "openDirectory" | "multiSelections")[];
        filters?: Array<{ name: string; extensions: string[] }>;
      }): Promise<string[] | null>;
      showSaveDialog(options: {
        title?: string;
        defaultPath?: string;
        filters?: Array<{ name: string; extensions: string[] }>;
      }): Promise<string | null>;

      // 7D — App version (auto-update disabled)
      getAppVersion(): Promise<string>;

      // Misc
      getPlatform(): Promise<"darwin" | "win32" | "linux">;
    };
  }
}

// ── Runtime helpers ─────────────────────────────────────────────────────────

/** Returns true when rendered inside an Electron BrowserWindow. */
export function isElectron(): boolean {
  return (
    typeof navigator !== "undefined" &&
    /electron/i.test(navigator.userAgent)
  );
}

// ── 7A: Window controls ─────────────────────────────────────────────────────

export function electronMinimize(): void {
  window.electronAPI?.minimizeWindow();
}

export function electronMaximize(): void {
  window.electronAPI?.maximizeWindow();
}

export function electronClose(): void {
  window.electronAPI?.closeWindow();
}

// ── 7B: System tray ─────────────────────────────────────────────────────────

/**
 * Push the current mission status to the system tray icon.
 * No-op in the browser.
 */
export function electronUpdateTray(payload: {
  activeMissions: number;
  status: "live" | "offline";
}): void {
  if (!isElectron()) return;
  window.electronAPI?.updateTray(payload);
}

// ── 7C: File system ─────────────────────────────────────────────────────────

/**
 * Open Electron's native directory/file picker. Returns selected paths,
 * or `null` when cancelled or running outside Electron.
 */
export async function electronShowOpenDialog(options: {
  title?: string;
  properties?: ("openFile" | "openDirectory" | "multiSelections")[];
  filters?: Array<{ name: string; extensions: string[] }>;
} = {}): Promise<string[] | null> {
  if (!isElectron() || !window.electronAPI) return null;
  return window.electronAPI.showOpenDialog(options);
}

/**
 * Open Electron's native save-file dialog. Returns the chosen path,
 * or `null` when cancelled or running outside Electron.
 */
export async function electronShowSaveDialog(options: {
  title?: string;
  defaultPath?: string;
  filters?: Array<{ name: string; extensions: string[] }>;
} = {}): Promise<string | null> {
  if (!isElectron() || !window.electronAPI) return null;
  return window.electronAPI.showSaveDialog(options);
}

// ── 7D: App version ─────────────────────────────────────────────────────────
// Auto-update is disabled. Updates are delivered via the NSIS Windows installer.

/** Returns the running app version (e.g. "0.1.0") or null in the browser. */
export async function electronGetAppVersion(): Promise<string | null> {
  if (!isElectron() || !window.electronAPI) return null;
  return window.electronAPI.getAppVersion();
}
