/** Preload for the factory status / startup progress window. */
import { contextBridge, ipcRenderer } from "electron";
import { STARTING_WINDOW_ACTIONS, STARTING_WINDOW_CHANNEL } from "./wizard-ipc-channels";

export type StatusUpdate = {
  title?: string;
  detail?: string;
  step?: string;
  steps?: ReadonlyArray<{ id: string; label: string }>;
  progress?: number;
  log?: string;
  failed?: boolean;
};

contextBridge.exposeInMainWorld("startingAPI", {
  onStatus: (cb: (update: StatusUpdate | string) => void) => {
    ipcRenderer.on(STARTING_WINDOW_CHANNEL, (_event, update: StatusUpdate | string) => cb(update));
  },
  openLogs: () => ipcRenderer.send(STARTING_WINDOW_ACTIONS.OPEN_LOGS),
  hide: () => ipcRenderer.send(STARTING_WINDOW_ACTIONS.HIDE),
});
