import { describe, expect, it } from "vitest";
import { NAV_GROUPS, NAV_ITEMS, isNavItemActive } from "./navigation";

describe("navigation helpers", () => {
  it("flattens NAV_GROUPS into NAV_ITEMS", () => {
    expect(NAV_GROUPS.length).toBeGreaterThanOrEqual(3);
    expect(NAV_ITEMS.some((item) => item.href === "/missions")).toBe(true);
    expect(NAV_ITEMS.some((item) => item.href === "/missions/history")).toBe(true);
  });

  it("highlights only the longest matching nav item on nested routes", () => {
    expect(isNavItemActive("/", "/")).toBe(true);
    expect(isNavItemActive("/missions", "/")).toBe(false);

    // /missions/detail and /missions/output belong to /missions
    expect(isNavItemActive("/missions/detail", "/missions")).toBe(true);
    expect(isNavItemActive("/missions/output", "/missions")).toBe(true);
    expect(isNavItemActive("/missions/detail", "/missions/history")).toBe(false);

    // /missions/history should highlight Mission History, NOT Missions
    expect(isNavItemActive("/missions/history", "/missions/history")).toBe(true);
    expect(isNavItemActive("/missions/history", "/missions")).toBe(false);
  });
});
