/** Preload for the transient "starting backend" progress window. */
import { contextBridge, ipcRenderer } from "electron";
import { STARTING_WINDOW_CHANNEL } from "./wizard-ipc-channels";

contextBridge.exposeInMainWorld("startingAPI", {
  onStatus: (cb: (detail: string) => void) => {
    ipcRenderer.on(STARTING_WINDOW_CHANNEL, (_event, detail: string) => cb(detail));
  },
});
