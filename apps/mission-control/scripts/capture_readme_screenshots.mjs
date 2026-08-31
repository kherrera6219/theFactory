/**
 * Capture Mission Control screenshots for the README.
 *
 * Run against a live local stack:
 *   cd apps/mission-control
 *   node scripts/capture_readme_screenshots.mjs
 *
 * Writes PNGs to docs/screenshots/. The onboarding tour is dismissed via the
 * same localStorage key the app sets when a user clicks "Skip tour", because a
 * modal overlay renders on first visit and would otherwise cover every shot.
 */

import { chromium } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "..", "..", "..");
const OUT = resolve(REPO, "docs", "screenshots");

const BASE = process.env.MISSION_CONTROL_URL || "http://localhost:3100";

const PAGES = [
  ["01-home", "/", "Launch pad and system health"],
  ["02-chat", "/chat", "PM agent conversation and mission intake"],
  ["03-builder", "/builder", "Guided mission builder"],
  ["04-missions", "/missions", "Mission lifecycle control center"],
  ["05-mission-history", "/missions/history", "Full mission archive"],
  ["06-projects", "/projects", "Operations projects and audit trail"],
  ["07-agents", "/agents", "Agent and pod monitoring"],
  ["08-logicnodes", "/logicnodes", "Logic graph explorer"],
  ["09-protocol-bus", "/protocol-bus", "Live protocol stream"],
  ["10-alerts", "/alerts", "System alerts and health events"],
  ["11-performance", "/performance", "Mission throughput and latency"],
  ["12-databases", "/databases", "Database health and diagnostics"],
  ["13-repo-import", "/repo", "Local ZIP import and mission scoping"],
  ["14-audit-log", "/audit", "Chronological system activity"],
  ["15-settings", "/settings", "Local runtime and integration controls"],
];

async function main() {
  mkdirSync(OUT, { recursive: true });

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1, // 1600x1000 is ample for README display; 2x tripled repo weight
    colorScheme: "dark",
  });

  // Suppress the first-visit product tour before any page script runs.
  await context.addInitScript(() => {
    try {
      for (const key of Object.keys(window.localStorage)) {
        if (/tour|onboard|welcome/i.test(key)) window.localStorage.setItem(key, "true");
      }
      window.localStorage.setItem("hgr.tour.dismissed", "true");
      window.localStorage.setItem("missionControl.tourCompleted", "true");
    } catch {
      /* storage unavailable; the explicit Skip click below is the fallback */
    }
  });

  const page = await context.newPage();
  const failures = [];

  // A mission detail view is the most representative "app in use" shot, but the
  // route needs a real id. Ask the running gateway for one through the UI's own
  // proxy, so this needs no API key. Prefer a COMPLETE mission: it has a full
  // event timeline rather than a half-drawn one.
  await page.goto(`${BASE}/`, { waitUntil: "domcontentloaded" }).catch(() => {});
  const missionId = await page
    .evaluate(async () => {
      try {
        const res = await fetch("/api/gateway/v1/missions?limit=100");
        if (!res.ok) return null;
        const body = await res.json();
        const list = Array.isArray(body) ? body : body.missions || body.items || [];
        const pick =
          list.find((m) => (m.state || m.status) === "COMPLETE") || list[0] || null;
        return pick ? pick.mission_id || pick.id : null;
      } catch {
        return null;
      }
    })
    .catch(() => null);

  if (missionId) {
    PAGES.push([
      "16-mission-detail",
      `/missions/detail?id=${missionId}`,
      "Live mission detail: timeline, events and artifacts",
    ]);
  } else {
    console.log("note: no mission id available; skipping the detail view shot");
  }

  for (const [name, path, label] of PAGES) {
    const url = `${BASE}${path}`;
    try {
      // networkidle gives the cleanest shot for ordinary pages, but the live
      // views (Protocol Bus stream, Agents heartbeat polling) hold connections
      // open and never reach it. Fall back to domcontentloaded plus a settle
      // rather than failing, so a streaming page is still captured.
      let response;
      try {
        response = await page.goto(url, { waitUntil: "networkidle", timeout: 20_000 });
      } catch {
        response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30_000 });
        await page.waitForTimeout(4000);
      }
      const status = response ? response.status() : 0;

      // Fallback for the tour if the storage keys did not match.
      const skip = page.getByRole("button", { name: /skip tour/i });
      if (await skip.isVisible().catch(() => false)) {
        await skip.click().catch(() => {});
      }

      // Let charts and any late-arriving fetches settle.
      await page.waitForTimeout(2500);

      const file = resolve(OUT, `${name}.png`);
      await page.screenshot({ path: file, fullPage: false });
      console.log(`ok    ${String(status).padEnd(4)} ${name.padEnd(22)} ${label}`);
    } catch (error) {
      failures.push([name, String(error).split("\n")[0]]);
      console.log(`FAIL       ${name.padEnd(22)} ${String(error).split("\n")[0]}`);
    }
  }

  await browser.close();

  if (failures.length) {
    console.log(`\n${failures.length} page(s) failed to capture.`);
    process.exitCode = 1;
  } else {
    console.log(`\nCaptured ${PAGES.length} screenshots to docs/screenshots/`);
  }
}

main();
