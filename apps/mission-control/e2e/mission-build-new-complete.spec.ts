import { expect, test } from "@playwright/test";
import { attachOperatorSession } from "./test-helpers";

async function fulfillJson(route: any, status: number, body: unknown): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

test.beforeEach(async ({ page }) => {
  await attachOperatorSession(page);
});

test("mission-build-new-complete E2E flow", async ({ page }) => {
  const missionId = "mission-build-001";
  let missionState = "QUEUED";

  // Mock API requests using absolute URL matching to prevent any requests leaking to live gateway
  await page.route("**/api/gateway/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname.replace(/^\/api\/gateway(?=\/|$)/, "");
    const method = request.method();

    if (pathname === "/v1/missions" && method === "POST") {
      return fulfillJson(route, 200, {
        mission_id: missionId,
        prompt: "Build resilient multi-agent factory smelting intake stream.",
        state: "QUEUED",
        requested_target_language: "typescript",
        metadata: {},
        created_at: new Date().toISOString(),
      });
    }

    if (pathname === "/v1/missions" && method === "GET") {
      return fulfillJson(route, 200, [
        {
          mission_id: missionId,
          prompt: "Build resilient multi-agent factory smelting intake stream.",
          state: missionState,
          requested_target_language: "typescript",
          metadata: {},
          created_at: new Date().toISOString(),
        },
      ]);
    }

    if (pathname === `/v1/missions/${missionId}` && method === "GET") {
      return fulfillJson(route, 200, {
        mission_id: missionId,
        prompt: "Build resilient multi-agent factory smelting intake stream.",
        state: missionState,
        requested_target_language: "typescript",
        metadata: {},
        created_at: new Date().toISOString(),
      });
    }

    if (pathname === `/v1/missions/${missionId}/events` && method === "GET") {
      return fulfillJson(route, 200, [
        { event_type: "MISSION_QUEUED", new_state: "QUEUED", ts: new Date().toISOString() },
        { event_type: "MISSION_RUNNING", new_state: "RUNNING", ts: new Date().toISOString() },
        { event_type: "MISSION_COMPLETE", new_state: "COMPLETE", ts: new Date().toISOString() },
      ]);
    }

    if (pathname === `/v1/missions/${missionId}/chain-trace` && method === "GET") {
      return fulfillJson(route, 200, {
        mission_id: missionId,
        routing_enforced: true,
        routing_version: "v2",
        selected_agent_id: "AGENT-13-TS",
        intake_agent_id: "AGENT-01-PM",
        executive_agent_id: "AGENT-02-CEO",
        assigned_pod_manager_agent_id: "AGENT-12-PODA-MGR",
        assigned_specialist_agent_id: "AGENT-13-TS",
        pod_assignment: { mission_id: missionId, pod_name: "podA" },
        logicnode_count: 2,
        delivery_summary: {
          delivery_title: "Smelt Stream Module",
          delivery_summary: "Fully compiled, AST-validated smelt intake module.",
          primary_artifact_type: "source_code",
          usage_notes: "npm run test to verify smelt properties.",
        },
        build_artifacts: [
          {
            artifact_id: "art-001",
            artifact_type: "generated_code",
            file_path: "dist/index.js",
            bytes: 4096,
            created_at: new Date().toISOString(),
          },
        ],
      });
    }

    if (pathname === "/v1/operations/logicnodes" && method === "GET") {
      return fulfillJson(route, 200, []);
    }

    if (pathname === "/v1/operations/agents" && method === "GET") {
      return fulfillJson(route, 200, { agents: [] });
    }

    if (pathname === `/v1/missions/${missionId}/audit-reports` && method === "GET") {
      return fulfillJson(route, 200, []);
    }

    if (pathname === `/v1/missions/${missionId}/token-usage` && method === "GET") {
      return fulfillJson(route, 200, null);
    }

    if (pathname.startsWith("/v1/stream/state")) {
      return route.fulfill({
        status: 503,
        contentType: "text/plain",
        body: "Service Unavailable",
      });
    }

    return route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: `No mock route for ${method} ${pathname}` }),
    });
  });

  // Navigate to intake page and launch mission
  await page.goto("/missions");
  await expect(page.getByRole("heading", { name: "Mission Intake and Lifecycle" })).toBeVisible();

  await page.getByLabel("Mission prompt").fill("Build resilient multi-agent factory smelting intake stream.");
  await page.getByRole("button", { name: "Launch Mission" }).click();

  await expect(page.getByText(/accepted and queued/i)).toBeVisible();
  
  // Transition mock state to RUNNING then COMPLETE for E2E detail page checks
  missionState = "COMPLETE";

  await page.getByRole("link", { name: "View Live" }).first().click();

  // Detail verification
  await expect(page).toHaveURL(new RegExp(`/missions/detail\\?id=${missionId}`));
  await expect(page.getByText("Delivered")).toBeVisible();
  await expect(page.getByText("Smelt Stream Module")).toBeVisible();

  // The generated-code download link lives in the Artifacts tab (Phase 2B
  // tabbed layout); inactive tab panels are `hidden` and not in the a11y tree.
  await page.getByRole("tab", { name: "Artifacts" }).click();
  await expect(page.getByRole("link", { name: "Download generated code" }).first()).toBeVisible();
});
