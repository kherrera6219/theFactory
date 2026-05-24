/**
 * 7D â€” Auto-update management using electron-updater.
 *
 * electron-updater reads update metadata from the URL configured in
 * package.json's "build.publish" field. A typical GitHub Releases config:
 *
 *   "publish": {
 *     "provider": "github",
 *     "owner": "kherrera6219",
 *     "repo": "theFactory"
 *   }
 *
 * Install: npm install electron-updater --save-prod
 *          npm install electron-builder --save-dev
 *
 * Code-sign your builds with electron-builder before publishing â€” auto-update
 * requires valid signatures on macOS and will prompt the user on Windows.
 */

import { app, BrowserWindow, ipcMain } from "electron";
import { autoUpdater, UpdateInfo } from "electron-updater";
import { IPC_CHANNELS } from "../app/lib/electron-bridge";

export function setupUpdater(mainWindow: BrowserWindow | null): void {
  // Download silently in the background; install on next quit.
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  // Notify the renderer when a download finishes so the UI can prompt the user.
  autoUpdater.on("update-downloaded", (info: UpdateInfo) => {
    mainWindow?.webContents.send(IPC_CHANNELS.UPDATER_DOWNLOADED, {
      version: info.version,
    });
  });

  autoUpdater.on("error", (err: Error) => {
    // Log but do not crash â€” updates are non-critical.
    console.error("[updater] auto-update error:", err.message);
  });

  // â”€â”€ IPC handlers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

  ipcMain.handle(IPC_CHANNELS.UPDATER_GET_VERSION, () => app.getVersion());

  ipcMain.handle(IPC_CHANNELS.UPDATER_CHECK, async () => {
    try {
      const result = await autoUpdater.checkForUpdates();
      return {
        updateAvailable: result !== null && result.updateInfo.version !== app.getVersion(),
        version: result?.updateInfo.version,
      };
    } catch {
      return { updateAvailable: false };
    }
  });

  ipcMain.on(IPC_CHANNELS.UPDATER_INSTALL, () => {
    autoUpdater.quitAndInstall(false, true); // isSilent=false, isForceRunAfter=true
  });
}
