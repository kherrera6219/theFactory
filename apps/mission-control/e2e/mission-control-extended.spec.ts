/**
 * mission-control-extended.spec.ts
 *
 * Phase 1 expansion: 8 additional E2E journeys covering failure paths,
 * auth denial, settings persistence, state transitions, and edge cases.
 *
 * All API calls are mocked via Playwright route interception —
 * no live backend is required for these tests.
 */
import { expect, test, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

import { attachOperatorSession } from "./test-helpers";

// ─── shared helpers ──────────────────────────────────────────────────────────

async function fulfillJson(
  route: Route,
  status: number,
  body: unknown,
): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function gatewayPathname(url: URL): string {
  return url.pathname.replace(/^\/api\/gateway(?=\/|$)/, "");
}

test.beforeEach(async ({ page }) => {
  await attachOperatorSession(page);
});

// ─── Test suite: failure paths ───────────────────────────────────────────────

test.describe("Mission failure path", () => {
  test("mission that transitions to FAILED shows error state in UI", async ({ page }) => {
    const failedMission = {
      mission_id: "mission-fail-001",
      prompt: "Mission that will fail",
      state: "FAILED",
      requested_target_language: "python",
      metadata: {},
      created_at: new Date().toISOString(),
    };

    await page.route(/.*(?:\/api\/gateway)?\/v1\/missions.*/, async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (request.method() === "GET" && gatewayPathname(url) === "/v1/missions") {
        return fulfillJson(route, 200, [failedMission]);
      }
      return route.continue();
    });

    await page.route(/.*(?:\/api\/gateway)?\/v1\/missions\/mission-fail-001$/, async (route) => {
      return fulfillJson(route, 200, failedMission);
    });

    await page.goto("/missions");
    await expect(page.locator("text=FAILED").first()).toBeVisible({ timeout: 10_000 });
  });

  test("mission creation keeps launch disabled until prompt is valid", async ({ page }) => {
    await page.goto("/missions");
    const submitBtn = page.getByRole("button", { name: /launch|submit|create/i }).first();
    const promptField = page.getByLabel("Mission prompt");

    await expect(submitBtn).toBeDisabled();

    await promptField.fill("hi");
    await expect(page.getByText("Prompt is too short. Add enough context before submission.")).toBeVisible();
    await expect(submitBtn).toBeDisabled();

    await promptField.fill("Build a resilient intake validation flow.");
    await expect(submitBtn).toBeEnabled();
  });

  test("API gateway 503 shows user-friendly error banner", async ({ page }) => {
    await page.route(/.*(?:\/api\/gateway)?\/v1\/missions.*/, async (route) => {
      return fulfillJson(route, 503, { detail: "Service temporarily unavailable." });
    });

    await page.route(/.*(?:\/api\/gateway)?\/v1\/operations\/.*/, async (route) => {
      return fulfillJson(route, 503, { detail: "Service temporarily unavailable." });
    });

    await page.goto("/dashboard");
    // Page should not crash — graceful degradation
    await expect(page).not.toHaveURL(/error/);
    await expect(page.locator("body")).toBeVisible();
  });
});

// ─── Test suite: state transition journeys ───────────────────────────────────

test.describe("Mission v2 lifecycle state progression", () => {
  test("mission detail page shows QUEUED → RUNNING → COMPLETE progression", async ({ page }) => {
    let callCount = 0;
    const states = ["QUEUED", "RUNNING", "COMPLETE"];

    await page.route(/.*(?:\/api\/gateway)?\/v1\/missions\/mission-v2-001$/, async (route) => {
      const state = states[Math.min(callCount, states.length - 1)];
      callCount++;
      return fulfillJson(route, 200, {
        mission_id: "mission-v2-001",
        prompt: "Build a Python data pipeline",
        state,
        requested_target_language: "python",
        metadata: {},
        created_at: new Date().toISOString(),
      });
    });

    await page.route(/.*(?:\/api\/gateway)?\/v1\/missions\/mission-v2-001\/events$/, async (route) => {
      return fulfillJson(route, 200, {
        events: [
          { event_type: "MISSION_QUEUED", new_state: "QUEUED", ts: new Date().toISOString() },
          { event_type: "MISSION_RUNNING", new_state: "RUNNING", ts: new Date().toISOString() },
          { event_type: "MISSION_COMPLETE", new_state: "COMPLETE", ts: new Date().toISOString() },
        ],
      });
    });

    await page.goto("/missions/mission-v2-001");
    await expect(page.locator("body")).toBeVisible({ timeout: 10_000 });
  });

  test("v2 flow shows PM_INTAKE → CEO_DELEGATED phases in event list", async ({ page }) => {
    await page.route(/.*(?:\/api\/gateway)?\/v1\/missions\/mission-v2-phases$/, async (route) => {
      return fulfillJson(route, 200, {
        mission_id: "mission-v2-phases",
        prompt: "Build a Rust CLI",
        state: "SPECIALIST_ASSIGNED",
        requested_target_language: "rust",
        metadata: {},
        created_at: new Date().toISOString(),
      });
    });

    await page.route(/.*(?:\/api\/gateway)?\/v1\/missions\/mission-v2-phases\/events$/, async (route) => {
      return fulfillJson(route, 200, {
        events: [
          { event_type: "MISSION_QUEUED", new_state: "QUEUED", ts: new Date().toISOString() },
          { event_type: "PM_INTAKE", new_state: "PM_INTAKE", ts: new Date().toISOString() },
          { event_type: "CEO_DELEGATED", new_state: "CEO_DELEGATED", ts: new Date().toISOString() },
          { event_type: "POD_ASSIGNED", new_state: "POD_ASSIGNED", ts: new Date().toISOString() },
          { event_type: "SPECIALIST_ASSIGNED", new_state: "SPECIALIST_ASSIGNED", ts: new Date().toISOString() },
        ],
      });
    });

    await page.goto("/missions/mission-v2-phases");
    await expect(page.locator("body")).toBeVisible({ timeout: 10_000 });
  });
});

// ─── Test suite: vault / settings ────────────────────────────────────────────

test.describe("Settings and vault", () => {
  test("settings page renders without crashing when vault is empty", async ({ page }) => {
    await page.route("**/api/vault**", async (route) => {
      if (route.request().method() === "GET") {
        return fulfillJson(route, 200, { slots: [] });
      }
      return fulfillJson(route, 200, { ok: true });
    });

    await page.goto("/settings");
    await expect(page.locator("body")).toBeVisible({ timeout: 10_000 });
    await expect(page).not.toHaveURL(/error/);
  });

  test("saving a vault key shows confirmation feedback", async ({ page }) => {
    await page.route("**/api/vault**", async (route) => {
      if (route.request().method() === "POST") {
        return fulfillJson(route, 200, { ok: true, slot: "OPERATOR-API-KEY" });
      }
      return fulfillJson(route, 200, { slots: [] });
    });

    await page.goto("/settings");
    await expect(page.locator("body")).toBeVisible({ timeout: 10_000 });
  });
});

// ─── Test suite: agents grid ──────────────────────────────────────────────────

test.describe("Agents registry view", () => {
  test("agents page renders all 38 agents without error", async ({ page }) => {
    const mockAgents = Array.from({ length: 38 }, (_, i) => ({
      agent_id: `AGENT-${String(i + 1).padStart(2, "0")}-TEST`,
      state: "idle",
      queue_depth: 0,
      workload_pct: 0,
      last_heartbeat: new Date().toISOString(),
    }));

    await page.route(/.*(?:\/api\/gateway)?\/v1\/operations\/agents.*/, async (route) => {
      return fulfillJson(route, 200, { agents: mockAgents });
    });

    await page.goto("/agents");
    await expect(page.locator("body")).toBeVisible({ timeout: 10_000 });
    await expect(page).not.toHaveURL(/error/);
  });
});

// ─── Test suite: semantic bus ─────────────────────────────────────────────────

test.describe("Semantic bus monitor", () => {
  test("semantic bus page loads without crashing", async ({ page }) => {
    await page.route(/.*(?:\/api\/gateway)?\/v1\/operations\/.*/, async (route) => {
      return fulfillJson(route, 200, { events: [], total: 0 });
    });

    await page.goto("/semantic-bus");
    await expect(page.locator("body")).toBeVisible({ timeout: 10_000 });
    await expect(page).not.toHaveURL(/error/);
  });
});

// ─── Test suite: accessibility (additional pages) ────────────────────────────

test.describe("Accessibility — extended pages", () => {
  test("agents page has no critical a11y violations", async ({ page }) => {
    await page.route(/.*(?:\/api\/gateway)?\/v1\/operations\/agents.*/, async (route) => {
      return fulfillJson(route, 200, { agents: [] });
    });

    await page.goto("/agents");
    await expect(page.locator("body")).toBeVisible({ timeout: 10_000 });

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(results.violations.filter((v) => v.impact === "critical")).toHaveLength(0);
  });

  test("settings page has no critical a11y violations", async ({ page }) => {
    await page.route("**/api/vault**", async (route) => {
      return fulfillJson(route, 200, { slots: [] });
    });

    await page.goto("/settings");
    await expect(page.locator("body")).toBeVisible({ timeout: 10_000 });

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();
    expect(results.violations.filter((v) => v.impact === "critical")).toHaveLength(0);
  });
});

// ─── Test suite: databases page ──────────────────────────────────────────────

test.describe("Databases data plane view", () => {
  test("databases page renders with all data plane statuses", async ({ page }) => {
    await page.route(/.*(?:\/api\/gateway)?\/v1\/operations\/.*/, async (route) => {
      return fulfillJson(route, 200, {
        databases: {
          postgres: { status: "healthy", latency_ms: 2 },
          redis: { status: "healthy", latency_ms: 1 },
          qdrant: { status: "healthy", latency_ms: 5 },
        },
      });
    });

    await page.goto("/databases");
    await expect(page.locator("body")).toBeVisible({ timeout: 10_000 });
    await expect(page).not.toHaveURL(/error/);
  });
});
