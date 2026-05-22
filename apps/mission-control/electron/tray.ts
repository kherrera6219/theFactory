/**
 * 7B — System tray management.
 *
 * Creates the tray icon and context menu. The tray tooltip is updated by the
 * renderer via `electronUpdateTray()` → IPC_CHANNELS.TRAY_UPDATE → main.ts.
 *
 * Icon assets:
 *   public/tray-icon.png       — 16×16 default (all platforms)
 *   public/tray-icon@2x.png    — 32×32 for Retina macOS
 *   public/tray-icon-win.ico   — ICO for Windows (256×256 recommended)
 * Replace these with actual branded assets before shipping.
 */

import path from "path";
import { app, BrowserWindow, Menu, nativeImage, Tray } from "electron";

export function setupTray(mainWindow: BrowserWindow | null): Tray {
  const platform = process.platform;

  // Resolve platform-appropriate icon.
  const iconFile =
    platform === "win32"
      ? "tray-icon-win.ico"
      : platform === "darwin"
      ? "tray-icon.png"     // macOS uses template images (set via nativeImage.setTemplateImage)
      : "tray-icon.png";

  const iconPath = path.join(__dirname, "..", "public", iconFile);
  let icon: nativeImage;
  try {
    icon = nativeImage.createFromPath(iconPath);
    if (platform === "darwin") {
      icon.setTemplateImage(true); // Follows menu bar dark/light mode automatically.
    }
  } catch {
    icon = nativeImage.createEmpty(); // Graceful degradation if asset is missing.
  }

  const tray = new Tray(icon);
  tray.setToolTip("Mission Control — HolyGrail Refinery");

  function buildMenu() {
    return Menu.buildFromTemplate([
      {
        label: "Open Mission Control",
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
          }
        },
      },
      { type: "separator" },
      {
        label: "New Mission",
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
            mainWindow.webContents.send("navigate", "/chat");
          }
        },
      },
      {
        label: "View Missions",
        click: () => {
          if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
            mainWindow.webContents.send("navigate", "/missions");
          }
        },
      },
      { type: "separator" },
      {
        label: `Quit Mission Control`,
        click: () => app.quit(),
      },
    ]);
  }

  tray.setContextMenu(buildMenu());

  // Double-click shows the main window (Windows / Linux; macOS uses context menu).
  tray.on("double-click", () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  return tray;
}
