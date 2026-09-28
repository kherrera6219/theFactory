import { describe, expect, it, vi } from "vitest";

vi.mock("electron", () => ({
  app: { getAppPath: () => "" },
  Menu: { buildFromTemplate: vi.fn() },
  nativeImage: { createFromPath: vi.fn(), createEmpty: vi.fn() },
  Tray: vi.fn(),
}));

import { buildTrayTemplate, type TrayActions } from "./tray";

function actions(): TrayActions {
  return {
    showWindow: vi.fn(),
    showStatus: vi.fn(),
    openLogs: vi.fn(),
    startFactory: vi.fn(),
    stopFactory: vi.fn(),
    isAutoStartEnabled: vi.fn(() => false),
    setAutoStart: vi.fn(),
    quit: vi.fn(),
    quitAndStop: vi.fn(),
  };
}

const item = (template: ReturnType<typeof buildTrayTemplate>, label: string) => {
  const found = template.find((entry) => entry.label === label);
  if (!found) throw new Error(`no tray item "${label}"`);
  return found;
};

describe("tray menu", () => {
  it("shows the factory health as its first line", () => {
    expect(buildTrayTemplate("running", null, false, actions())[0].label).toBe("Factory running");
    expect(buildTrayTemplate("stopped", "Stopping factory…", false, actions())[0].label).toBe(
      "Stopping factory…",
    );
  });

  it("offers start only when stopped and stop only when running", () => {
    const running = buildTrayTemplate("running", null, false, actions());
    expect(item(running, "Start factory").enabled).toBe(false);
    expect(item(running, "Stop factory").enabled).toBe(true);
    const stopped = buildTrayTemplate("stopped", null, false, actions());
    expect(item(stopped, "Start factory").enabled).toBe(true);
    expect(item(stopped, "Stop factory").enabled).toBe(false);
  });

  it("disables lifecycle actions while one is in progress", () => {
    const busy = buildTrayTemplate("stopped", "Factory starting…", false, actions());
    expect(item(busy, "Start factory").enabled).toBe(false);
    expect(item(busy, "Quit and stop factory").enabled).toBe(false);
  });

  it("makes quitting keep the factory running unless the operator says otherwise", () => {
    const a = actions();
    const template = buildTrayTemplate("running", null, false, a);
    item(template, "Quit (factory keeps running)").click?.({} as never, undefined, {} as never);
    expect(a.quit).toHaveBeenCalled();
    expect(a.quitAndStop).not.toHaveBeenCalled();
  });

  it("reflects and toggles the opt-in Start with Windows setting", () => {
    const a = actions();
    const off = item(buildTrayTemplate("running", null, false, a), "Start with Windows");
    expect(off.checked).toBe(false);
    off.click?.({ checked: true } as never, undefined, {} as never);
    expect(a.setAutoStart).toHaveBeenCalledWith(true);
    expect(item(buildTrayTemplate("running", null, true, a), "Start with Windows").checked).toBe(true);
  });

  it("routes shortcuts to the right pages", () => {
    const a = actions();
    const template = buildTrayTemplate("running", null, false, a);
    item(template, "New Mission").click?.({} as never, undefined, {} as never);
    expect(a.showWindow).toHaveBeenCalledWith("/chat");
  });
});
