import { afterEach, describe, expect, it, vi } from "vitest";

import { isElectron } from "./electron-bridge";

/**
 * `isElectron()` used to sniff the user agent for "electron". That was wrong in
 * both directions.
 *
 * Every Electron-based browser — the Claude desktop app, VS Code's Simple
 * Browser, Slack, Discord — carries "Electron/x.y.z" in its UA. Opening Mission
 * Control in one made this return true, so `api-client` took the desktop branch
 * and called the API gateway directly instead of the same-origin
 * `/api/gateway` proxy that attaches operator credentials. Every request came
 * back 401 (observed live 2026-08-04 while driving the app through an
 * Electron-based browser).
 *
 * The fix detects the capability the callers actually depend on:
 * `window.electronAPI`, injected by the preload script.
 */

const originalDescriptor = Object.getOwnPropertyDescriptor(globalThis, "window");

afterEach(() => {
  if (originalDescriptor) {
    Object.defineProperty(globalThis, "window", originalDescriptor);
  }
  vi.unstubAllGlobals();
});

function withWindow(value: Record<string, unknown> | undefined) {
  vi.stubGlobal("window", value);
}

describe("isElectron", () => {
  it("is true when the preload bridge is present", () => {
    withWindow({ electronAPI: { minimizeWindow: () => {} } });
    expect(isElectron()).toBe(true);
  });

  it("is false in a plain browser", () => {
    withWindow({});
    expect(isElectron()).toBe(false);
  });

  it("is false in another app's Electron shell", () => {
    // The exact user agent that caused the live 401s. Without the preload
    // bridge this is someone else's Electron, not ours.
    withWindow({
      navigator: {
        userAgent:
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) " +
          "Claude/1.24012.11 Chrome/148.0.7778.280 Electron/42.7.0 Safari/537.36 MSIX",
      },
    });
    expect(isElectron()).toBe(false);
  });

  it("does not depend on the user agent at all", () => {
    // A packaged build whose UA lacked "electron" must still be detected.
    withWindow({
      electronAPI: { minimizeWindow: () => {} },
      navigator: { userAgent: "Mozilla/5.0 (Windows NT 10.0) Chrome/148.0.0.0 Safari/537.36" },
    });
    expect(isElectron()).toBe(true);
  });

  it("is false during server-side rendering", () => {
    withWindow(undefined);
    expect(isElectron()).toBe(false);
  });
});
