"use client";

import { useEffect, useState } from "react";
import {
  isElectron,
  electronMinimize,
  electronMaximize,
  electronClose,
} from "../lib/electron-bridge";

/**
 * 7A — Custom frameless window titlebar for Electron.
 *
 * Rendered only when `isElectron()` is true; returns null in the browser.
 * The `shell` element must have `padding-top` equal to the titlebar height
 * (set via `--electron-titlebar-h` CSS var) when this component is active.
 *
 * BrowserWindow must be created with `frame: false` (or `titleBarStyle: "hidden"`)
 * for this component to replace the native titlebar.
 *
 * The `.electron-titlebar-drag` region sets `-webkit-app-region: drag` so the
 * user can drag the window by clicking anywhere in the titlebar except the
 * control buttons (which set `-webkit-app-region: no-drag`).
 */
export function ElectronTitlebar() {
  const [inElectron] = useState(() => isElectron());
  const [maximized, setMaximized] = useState(false);
  const [platform, setPlatform] = useState<"darwin" | "win32" | "linux">("win32");

  useEffect(() => {
    if (!inElectron || !window.electronAPI) return;

    // Initial state
    void window.electronAPI.isMaximized().then(setMaximized);
    void window.electronAPI.getPlatform().then(setPlatform);

    // Subscribe to maximize/restore events.
    const cleanup = window.electronAPI.onWindowStateChange((max) => setMaximized(max));
    return cleanup;
  }, [inElectron]);

  if (!inElectron) return null;

  const isMac = platform === "darwin";

  return (
    <div className={`electron-titlebar${isMac ? " electron-titlebar-mac" : ""}`}>
      {/* macOS: traffic lights are on the left; drag region takes up the middle. */}
      {isMac ? (
        <>
          {/* macOS window controls are rendered by the OS in the frame overlay area;
              we expose a no-drag zone where they appear so clicks reach the OS controls. */}
          <div className="electron-titlebar-mac-traffic" aria-hidden="true" />
          <div className="electron-titlebar-drag" aria-hidden="true" />
          <span className="electron-titlebar-title" aria-hidden="true">
            Mission Control
          </span>
          <div style={{ width: 80 }} />
        </>
      ) : (
        <>
          {/* Windows / Linux: logo + drag + controls on right. */}
          <div className="electron-titlebar-drag" aria-hidden="true" />
          <span className="electron-titlebar-title" aria-hidden="true">
            Mission Control — HolyGrail Refinery
          </span>
          <div className="electron-titlebar-controls" aria-label="Window controls">
            <button
              type="button"
              className="titlebar-btn titlebar-minimize"
              aria-label="Minimize window"
              onClick={electronMinimize}
            >
              {/* Win11-style minimize glyph */}
              <svg width="10" height="1" viewBox="0 0 10 1" aria-hidden="true">
                <rect width="10" height="1" fill="currentColor" />
              </svg>
            </button>
            <button
              type="button"
              className="titlebar-btn titlebar-maximize"
              aria-label={maximized ? "Restore window" : "Maximize window"}
              onClick={electronMaximize}
            >
              {maximized ? (
                /* Restore icon */
                <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                  <path
                    d="M3 0H10V7H8V2H3V0ZM0 3H7V10H0V3Z"
                    fill="currentColor"
                    fillRule="evenodd"
                  />
                </svg>
              ) : (
                /* Maximize icon */
                <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                  <path
                    d="M0 0H10V10H0V0ZM1 1V9H9V1H1Z"
                    fill="currentColor"
                    fillRule="evenodd"
                  />
                </svg>
              )}
            </button>
            <button
              type="button"
              className="titlebar-btn titlebar-close"
              aria-label="Close window"
              onClick={electronClose}
            >
              <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
                <path
                  d="M1 0L0 1L4 5L0 9L1 10L5 6L9 10L10 9L6 5L10 1L9 0L5 4L1 0Z"
                  fill="currentColor"
                />
              </svg>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
