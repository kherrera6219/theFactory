/**
 * Preload script for the first-run setup wizard window only -- deliberately
 * separate from the main app's preload.ts/electron-bridge.ts contract so
 * this one-time flow doesn't touch the primary app's IPC surface.
 */
import { contextBridge, ipcRenderer } from "electron";
import { SETUP_WIZARD_CHANNELS } from "./wizard-ipc-channels";

contextBridge.exposeInMainWorld("setupWizardAPI", {
  submit: (keys: { gemini: string; openai: string; anthropic: string }) =>
    ipcRenderer.send(SETUP_WIZARD_CHANNELS.SUBMIT, keys),
  quit: () => ipcRenderer.send(SETUP_WIZARD_CHANNELS.QUIT),
});
