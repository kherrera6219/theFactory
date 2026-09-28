/**
 * System tray: the app's home while the window is closed.
 *
 * Operator decision (2026-09-27): closing the window keeps theFactory running
 * in the tray -- missions in flight are never interrupted by closing a window.
 * The tray shows live factory health and offers the explicit actions:
 * start/stop the factory, quit (factory keeps running) or quit and stop it,
 * and the opt-in "Start with Windows" setting (off by default).
 */

import path from "path";
import { app, Menu, nativeImage, Tray, type MenuItemConstructorOptions, type NativeImage } from "electron";
import { healthLabel, type FactoryHealth } from "./factory-stack";

export type TrayActions = {
  showWindow: (route?: string) => void;
  showStatus: () => void;
  openLogs: () => void;
  startFactory: () => void;
  stopFactory: () => void;
  isAutoStartEnabled: () => boolean;
  setAutoStart: (enabled: boolean) => void;
  quit: () => void;
  quitAndStop: () => void;
};

export type TrayController = {
  setHealth: (health: FactoryHealth) => void;
  setBusy: (busy: string | null) => void;
  refresh: () => void;
  destroy: () => void;
};

/** Pure menu model, exported for tests. */
export function buildTrayTemplate(
  health: FactoryHealth,
  busy: string | null,
  autoStart: boolean,
  actions: TrayActions,
): MenuItemConstructorOptions[] {
  const running = health === "running" || health === "starting";
  return [
    { label: busy ?? healthLabel(health), enabled: false },
    { type: "separator" },
    { label: "Open Mission Control", click: () => actions.showWindow() },
    { label: "New Mission", click: () => actions.showWindow("/chat") },
    { label: "View Missions", click: () => actions.showWindow("/missions") },
    { type: "separator" },
    { label: "Show factory status", click: () => actions.showStatus() },
    {
      label: "Start factory",
      enabled: !busy && !running,
      click: () => actions.startFactory(),
    },
    {
      label: "Stop factory",
      enabled: !busy && running,
      click: () => actions.stopFactory(),
    },
    { label: "Open logs folder", click: () => actions.openLogs() },
    { type: "separator" },
    {
      label: "Start with Windows",
      type: "checkbox",
      checked: autoStart,
      click: (item) => actions.setAutoStart(Boolean(item.checked)),
    },
    { type: "separator" },
    { label: "Quit (factory keeps running)", click: () => actions.quit() },
    { label: "Quit and stop factory", enabled: !busy, click: () => actions.quitAndStop() },
  ];
}

function loadIcon(): NativeImage {
  const file = process.platform === "win32" ? "tray-icon-win.ico" : "tray-icon.png";
  // Unpackaged: <app>/public. Packaged: public/ only ships inside the
  // standalone server bundle (scripts/build-electron.mjs copies it there).
  const candidates = [
    path.join(app.getAppPath(), "public", file),
    path.join(app.getAppPath(), ".next", "standalone", "public", file),
  ];
  for (const candidate of candidates) {
    const icon = nativeImage.createFromPath(candidate);
    if (!icon.isEmpty()) return icon;
  }
  return nativeImage.createEmpty(); // Graceful degradation if the asset is missing.
}

export function setupTray(actions: TrayActions): TrayController {
  const tray = new Tray(loadIcon());
  let health: FactoryHealth = "starting";
  let busy: string | null = null;

  const refresh = () => {
    tray.setToolTip(`theFactory Mission Control — ${busy ?? healthLabel(health)}`);
    tray.setContextMenu(
      Menu.buildFromTemplate(buildTrayTemplate(health, busy, actions.isAutoStartEnabled(), actions)),
    );
  };

  tray.on("double-click", () => actions.showWindow());
  tray.on("click", () => actions.showWindow());
  refresh();

  return {
    setHealth: (next) => {
      if (next !== health) {
        health = next;
        refresh();
      }
    },
    setBusy: (next) => {
      busy = next;
      refresh();
    },
    refresh,
    destroy: () => tray.destroy(),
  };
}
