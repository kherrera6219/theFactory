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

test("mission-cost-panel details and cost distribution", async ({ page }) => {
  const missionId = "mission-cost-999";

  const mockTokenUsage = {
    mission_id: missionId,
    total_tokens: 154000,
    total_input_tokens: 120000,
    total_output_tokens: 34000,
    estimated_cost_usd: 1.7450,
    call_count: 14,
    unknown_pricing_count: 0,
    by_provider: [
      {
        provider: "anthropic",
        model: "claude-3-5-sonnet",
        input_tokens: 80000,
        output_tokens: 20000,
        estimated_cost_usd: 1.2000,
        call_count: 8,
      },
      {
        provider: "openai",
        model: "gpt-5.5",
        input_tokens: 40000,
        output_tokens: 14000,
        estimated_cost_usd: 0.5450,
        call_count: 6,
      },
    ],
    by_agent: [
      {
        agent_id: "AGENT-02-CEO",
        provider: "anthropic",
        model: "claude-3-5-sonnet",
        input_tokens: 50000,
        output_tokens: 10000,
        cost_usd: 0.7500,
        call_count: 4,
      },
      {
        agent_id: "AGENT-14-PYTHON",
        provider: "openai",
        model: "gpt-5.5",
        input_tokens: 40000,
        output_tokens: 14000,
        cost_usd: 0.5450,
        call_count: 6,
      },
    ],
  };

  // Mock API requests using absolute URL matching to prevent any requests leaking to live gateway
  await page.route("**/api/gateway/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname.replace(/^\/api\/gateway(?=\/|$)/, "");
    const method = request.method();

    if (pathname === `/v1/missions/${missionId}` && method === "GET") {
      return fulfillJson(route, 200, {
        mission_id: missionId,
        prompt: "Measure pipeline costs.",
        state: "RUNNING",
        requested_target_language: "python",
        metadata: {},
        created_at: new Date().toISOString(),
      });
    }

    if (pathname === `/v1/missions/${missionId}/token-usage` && method === "GET") {
      return fulfillJson(route, 200, mockTokenUsage);
    }

    if (pathname === `/v1/missions/${missionId}/events` && method === "GET") {
      return fulfillJson(route, 200, []);
    }

    if (pathname === `/v1/missions/${missionId}/chain-trace` && method === "GET") {
      return fulfillJson(route, 200, {
        mission_id: missionId,
        routing_enforced: true,
        logicnode_count: 0,
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

  await page.goto(`/missions/${missionId}`);
  await expect(page.locator("body")).toBeVisible();

  // Verify elements in the CostPanel are fully populated
  await expect(page.getByText("Token Usage & Cost Analysis")).toBeVisible();
  await expect(page.getByText("$1.7450")).toBeVisible();
  await expect(page.getByText("154,000")).toBeVisible();
  await expect(page.getByText("120,000 in / 34,000 out")).toBeVisible();
  await expect(page.locator(".cost-analysis-panel").getByText("14", { exact: true })).toBeVisible();

  // Verify provider breakdown
  await expect(page.getByText("anthropic", { exact: true })).toBeVisible();
  await expect(page.getByText("claude-3-5-sonnet", { exact: true })).toBeVisible();
  await expect(page.getByText("$1.2000")).toBeVisible();

  // Verify agent breakdown
  await expect(page.getByText("AGENT-14-PYTHON")).toBeVisible();
  await expect(page.getByText("$0.5450").first()).toBeVisible();
});
