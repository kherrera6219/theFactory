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

test("mission-reduce-deps SBOM reduction and dependency classifications", async ({ page }) => {
  const missionId = "mission-deps-444";

  const mockChainTrace = {
    mission_id: missionId,
    routing_enforced: true,
    logicnode_count: 3,
    dependency_inventory: {
      dependency_count: 10,
      sources: ["package.json", "requirements.txt"],
      inventory_id: "inv-deps-444",
    },
    dependency_classification_report: {
      classifications: [
        {
          dependency_id: "dep-lodash",
          name: "lodash",
          decision: "ABSORB",
          risk_level: "low",
          safety_blocked: false,
          blocking: false,
          rationale: "Used only for small array utilities. Can absorb into local codebase.",
          source_refs: ["package.json:L12"],
        },
        {
          dependency_id: "dep-moment",
          name: "moment",
          decision: "REPLACE",
          risk_level: "medium",
          safety_blocked: false,
          blocking: false,
          rationale: "Deprecate in favor of native Date/Intl methods to improve bundle size.",
          source_refs: ["package.json:L14"],
        },
      ],
    },
    dependency_absorption_report: {
      status: "COMPLETED",
      blocking: false,
      safety_block_count: 0,
      modified_output_created: true,
      equivalence_passed: true,
      security_compliance_passed: true,
      recommendations: ["Absorb lodash", "Replace moment"],
      planned_replacements: [
        {
          dependency_id: "dep-moment",
          name: "moment",
          status: "SUCCESSFUL",
          blocked_by: [],
        },
      ],
    },
    depabs_execution: {
      status: "SUCCESS",
      absorption_count: 1,
      splices: [
        {
          library: "lodash",
          status: "SPLICED",
          reason: "Spliced local array utilities directly into the source bundle.",
        },
      ],
    },
    sbom_delta: {
      reduction_percent: 20.0,
      original_dependency_count: 10,
      removed: ["lodash", "moment"],
      remaining: ["react", "next", "tailwindcss", "typescript"],
    },
    dependency_survival_justifications: [
      {
        justification_id: "just-react",
        name: "react",
        decision: "SURVIVE",
        rationale: "Core UI rendering library. Unfeasible to rewrite locally.",
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
        prompt: "Reduce dependencies in the package.",
        state: "VERIFIED",
        requested_target_language: "typescript",
        metadata: {},
        created_at: new Date().toISOString(),
      });
    }

    if (pathname === `/v1/missions/${missionId}/events` && method === "GET") {
      return fulfillJson(route, 200, []);
    }

    if (pathname === `/v1/missions/${missionId}/chain-trace` && method === "GET") {
      return fulfillJson(route, 200, mockChainTrace);
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

  await page.goto(`/missions/detail?id=${missionId}`);
  await expect(page.locator("body")).toBeVisible();

  // Dependency Absorption lives in the Artifacts tab (Phase 2B tabbed layout);
  // inactive tab panels are `hidden` and excluded from the accessibility tree.
  await page.getByRole("tab", { name: "Artifacts" }).click();

  // Verify Dependency Absorption Header
  await expect(page.getByText("Dependency Absorption")).toBeVisible();

  // Verify Inventory Section
  await expect(page.getByText("10", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("package.json, requirements.txt")).toBeVisible();
  await expect(page.getByText("inv-deps-444")).toBeVisible();

  // Verify Classification Report cards
  await expect(page.getByRole("heading", { name: "lodash", exact: true })).toBeVisible();
  await expect(page.getByText("ABSORB", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Used only for small array utilities. Can absorb into local codebase.")).toBeVisible();
  await expect(page.getByText("package.json:L12")).toBeVisible();

  await expect(page.getByRole("heading", { name: "moment", exact: true })).toBeVisible();
  await expect(page.getByText("REPLACE", { exact: true }).first()).toBeVisible();

  // Verify SBOM Delta
  await expect(page.getByText("SBOM delta")).toBeVisible();
  await expect(page.getByText("20%")).toBeVisible();
  await expect(page.getByText("lodash, moment")).toBeVisible();

  // Verify Survival Justifications
  await expect(page.getByText("Survival justifications")).toBeVisible();
  await expect(page.getByText("Core UI rendering library. Unfeasible to rewrite locally.")).toBeVisible();
});
