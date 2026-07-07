/**
 * IPC channel names shared between main.ts and the setup/starting preload
 * scripts. Kept separate from the preload scripts themselves because those
 * call contextBridge.exposeInMainWorld() at module load time, which throws
 * if required from the main process (contextBridge is only defined in a
 * preload script's execution context).
 */
export const SETUP_WIZARD_CHANNELS = {
  SUBMIT: "setup-wizard:submit",
  QUIT: "setup-wizard:quit",
} as const;

export const STARTING_WINDOW_CHANNEL = "starting-window:status";
