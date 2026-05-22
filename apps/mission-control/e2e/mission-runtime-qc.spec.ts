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

test("mission-runtime-qc Docker reports and stdout logs rendering", async ({ page }) => {
  const missionId = "mission-qc-777";

  const mockChainTrace = {
    mission_id: missionId,
    routing_enforced: true,
    logicnode_count: 1,
    testdata_manifest: {
      base_image: "python:3.11-slim",
      test_framework: "pytest",
      run_command: "pytest tests/services/pod-worker/ --tb=short",
      timeout_seconds: 30,
      memory_limit_mb: 512,
      synthetic_inputs: [
        { name: "input_a", type: "string" },
        { name: "input_b", type: "number" },
      ],
    },
    runtime_qc_report: {
      verdict: "SUCCESS",
      execution_type: "docker_sandbox",
      stdout_preview: "=== test session starts ===\nplatform linux -- Python 3.11.8\npassed 12 tests in 2.11 seconds\n",
      qc_assessment: {
        qc_verdict: "VERIFIED",
        deployment_safe: true,
        findings: [
          "Zero critical CVEs in base image.",
          "Tests passed with 100% equivalence coverage.",
        ],
      },
    },
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
        prompt: "Verify execution with QC checks.",
        state: "VERIFIED",
        requested_target_language: "python",
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

  await page.goto(`/missions/${missionId}`);
  await expect(page.locator("body")).toBeVisible();

  // Verify Runtime QC headers
  await expect(page.getByText("Runtime QC")).toBeVisible();
  
  // Verify execution report fields
  await expect(page.getByText("docker_sandbox")).toBeVisible();
  await expect(page.locator("dd").filter({ hasText: "VERIFIED" }).first()).toBeVisible();
  await expect(page.getByText("yes").first()).toBeVisible();

  // Verify stdout log preview
  await expect(page.locator("pre.code-preview")).toContainText("passed 12 tests in 2.11 seconds");

  // Verify findings
  await expect(page.getByText("Zero critical CVEs in base image.")).toBeVisible();
  await expect(page.getByText("Tests passed with 100% equivalence coverage.")).toBeVisible();

  // Verify test environment manifest fields
  await expect(page.getByText("python:3.11-slim")).toBeVisible();
  await expect(page.getByText("pytest", { exact: true })).toBeVisible();
  await expect(page.getByText("pytest tests/services/pod-worker/ --tb=short")).toBeVisible();
  await expect(page.getByText("30s / 512MB")).toBeVisible();
  await expect(page.getByText("2", { exact: true })).toBeVisible(); // Synthetic inputs count
});
