/**
 * 7D — App version IPC handler.
 *
 * Auto-update has been intentionally disabled. Updates are handled manually
 * via the Windows installer (NSIS). This module exists only to expose the
 * current app version to the renderer so the UI can display it.
 */

import { app, ipcMain } from "electron";
import { IPC_CHANNELS } from "../app/lib/electron-bridge";

export function setupUpdater(): void {
  ipcMain.handle(IPC_CHANNELS.UPDATER_GET_VERSION, () => app.getVersion());
}
