import { expect, test, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

type MockOptions = {
  failMissionList?: boolean;
  failMissionCreate?: boolean;
};

type MissionRecord = {
  mission_id: string;
  prompt?: string;
  state: string;
  requested_target_language: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
};

function personaProfile(agentId: string) {
  return {
    job_role: {
      title: "Principal Mission Agent",
      primary_function: "Coordinate mission delivery",
      scope: `Operational scope for ${agentId}`,
    },
    education_certifications: ["B.S. Computer Science", "SRE Practitioner"],
    traits_skills: ["Systems thinking", "Incident triage"],
    methods_procedures: ["Runbook-first diagnostics", "Risk-first planning"],
    tools: ["Prometheus", "Grafana", "Playwright"],
    master_instruction: "Deliver safely with measurable reliability outcomes.",
    protocol: {
      primary_code: "ALPHA",
      primary_name: "Directive",
      primary_purpose: "Mission planning",
      message_format: "JSON",
      supported_codes: ["ALPHA", "BETA"],
      supported_names: ["Directive", "Production"],
    },
    api_configuration: {
      api_key_env_var: `${agentId}_API_KEY`,
      api_slot_id: `${agentId}-API-KEY`,
      context_window_tokens: 32_000,
      cached_content: [],
      model_routing: {
        provider: "openai",
        model: "gpt-4.1",
      },
    },
    standards_alignment: [
      {
        standard_id: "NIST-CSF-2.0",
        framework: "NIST CSF",
        version: "2.0",
        role_mapping: "Operational resilience",
        focus_areas: ["Detect", "Respond"],
      },
    ],
    evidence_sources: [
      {
        source_id: "NIST-CSF-2.0",
        title: "NIST Cybersecurity Framework",
        organization: "NIST",
        version: "2.0",
        url: "https://www.nist.gov/cyberframework",
        last_verified: "2026-03-03T00:00:00.000Z",
        applicability: "Mission runtime controls",
      },
    ],
  };
}

async function fulfillJson(route: Route, status: number, body: unknown): Promise<void> {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function setupMissionControlApiMocks(page: Page, options: MockOptions = {}): Promise<void> {
  const seedMissionId = "mission-seed-001";
  let missionCounter = 1;

  let missions: MissionRecord[] = [
    {
      mission_id: seedMissionId,
      prompt: "Seed mission for dashboard and mission list.",
      state: "VERIFIED",
      requested_target_language: "python",
      metadata: { source: "seed" },
      created_at: "2026-03-03T11:59:00.000Z",
    },
  ];

  const missionEvents = new Map<string, Record<string, unknown>[]>([
    [
      seedMissionId,
      [
        {
          previous_state: "RUNNING",
          new_state: "VERIFIED",
          event_type: "mission.state.transition",
          ts: "2026-03-03T11:59:30.000Z",
        },
      ],
    ],
  ]);

  const missionLogicNodes = new Map<string, Record<string, unknown>[]>([
    [
      seedMissionId,
      [
        {
          mission_id: seedMissionId,
          node_id: "logic-001",
          node: { status: "VERIFIED", confidence: 0.96 },
          created_at: "2026-03-03T11:59:45.000Z",
        },
      ],
    ],
  ]);

  await page.route("**/api/repo/import", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      return fulfillJson(route, 405, { detail: "Method not allowed." });
    }
    const payload = (request.postDataJSON() as Record<string, unknown>) ?? {};
    const repoUrl = typeof payload.repo_url === "string" ? payload.repo_url : "";
    if (!repoUrl.startsWith("https://github.com/")) {
      return fulfillJson(route, 400, { detail: "Invalid repository URL." });
    }

    return fulfillJson(route, 200, {
      repository: {
        owner: "octo",
        repo: "sample-platform",
        branch: "main",
        default_branch: "main",
        private: false,
        html_url: "https://github.com/octo/sample-platform",
      },
      files: [
        {
          path: "apps/mission-control/app/(shell)/repo/page.tsx",
          language: "TypeScript",
          bytes: 12_000,
          estimated_lines: 260,
        },
        {
          path: "services/api-gateway/api_gateway/main.py",
          language: "Python",
          bytes: 9_400,
          estimated_lines: 210,
        },
        {
          path: "README.md",
          language: "Markdown",
          bytes: 1_800,
          estimated_lines: 40,
        },
      ],
      stats: {
        total_files: 3,
        estimated_total_lines: 510,
        selected_subdirectory: "/",
        truncated: false,
        skipped_large_files: 0,
      },
      logs: [
        "Validated repository request payload.",
        "Resolving metadata for octo/sample-platform.",
        "Fetched repository tree with 3 entries.",
        "Selected 3 files from /.",
      ],
    });
  });

  await page.route("http://localhost:8100/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = url.pathname;

    if (pathname === "/v1/missions" && request.method() === "GET") {
      if (options.failMissionList) {
        return fulfillJson(route, 503, { detail: "Mission list unavailable for test." });
      }
      const limit = Number(url.searchParams.get("limit") ?? "20");
      const capped = Number.isFinite(limit) ? Math.max(1, limit) : 20;
      return fulfillJson(route, 200, missions.slice(0, capped));
    }

    if (pathname === "/v1/missions" && request.method() === "POST") {
      if (options.failMissionCreate) {
        return fulfillJson(route, 500, { detail: "Mission creation forced failure." });
      }
      const payload = (request.postDataJSON() as Record<string, unknown>) ?? {};
      const missionId = `mission-e2e-${String(missionCounter).padStart(3, "0")}`;
      missionCounter += 1;
      const mission: MissionRecord = {
        mission_id: missionId,
        prompt: typeof payload.prompt === "string" ? payload.prompt : "Mission from e2e test",
        state: "RUNNING",
        requested_target_language:
          typeof payload.requested_target_language === "string"
            ? payload.requested_target_language
            : null,
        metadata:
          payload.metadata && typeof payload.metadata === "object"
            ? (payload.metadata as Record<string, unknown>)
            : {},
        created_at: new Date().toISOString(),
      };
      missions = [mission, ...missions];
      missionEvents.set(missionId, [
        {
          previous_state: "QUEUED",
          new_state: "RUNNING",
          event_type: "mission.state.transition",
          ts: new Date().toISOString(),
        },
      ]);
      missionLogicNodes.set(missionId, [
        {
          mission_id: missionId,
          node_id: "logic-e2e-001",
          node: { status: "VERIFIED", confidence: 0.92 },
          created_at: new Date().toISOString(),
        },
      ]);
      return fulfillJson(route, 200, mission);
    }

    const missionMatch = pathname.match(/^\/v1\/missions\/([^/]+)$/);
    if (missionMatch && request.method() === "GET") {
      const missionId = decodeURIComponent(missionMatch[1]);
      const mission = missions.find((item) => item.mission_id === missionId);
      if (!mission) {
        return fulfillJson(route, 404, { detail: "Mission not found." });
      }
      return fulfillJson(route, 200, mission);
    }

    const missionEventsMatch = pathname.match(/^\/v1\/missions\/([^/]+)\/events$/);
    if (missionEventsMatch && request.method() === "GET") {
      const missionId = decodeURIComponent(missionEventsMatch[1]);
      const limit = Number(url.searchParams.get("limit") ?? "20");
      const capped = Number.isFinite(limit) ? Math.max(1, limit) : 20;
      const events = missionEvents.get(missionId) ?? [];
      return fulfillJson(route, 200, events.slice(0, capped));
    }

    if (pathname === "/v1/operations/agents" && request.method() === "GET") {
      const activeMissionId = missions[0]?.mission_id ?? seedMissionId;
      const agent = {
        index: 1,
        agent_id: "AGENT-01-PM",
        short_code: "PM",
        name: "Agent One PM",
        tier: "manager",
        pod: "core",
        role: "Program Manager",
        category: "management",
        specialties: ["planning", "coordination"],
        state: "RUNNING",
        queue_depth: 1,
        workload_pct: 60,
        last_heartbeat_iso: new Date().toISOString(),
        active_mission_ids: [activeMissionId],
        persona_profile: personaProfile("AGENT-01-PM"),
      };
      return fulfillJson(route, 200, {
        generated_at: new Date().toISOString(),
        total_agents: 1,
        runtime: {
          redis_ready: true,
          db_ready: true,
          protocol_ready: true,
          consumer_running: true,
        },
        mission_backlog: {
          active: 1,
          verified: missions.filter((item) => item.state === "VERIFIED").length,
          complete: missions.filter((item) => item.state === "COMPLETE").length,
          assigned_active: 1,
        },
        tier_counts: { manager: 1 },
        pod_counts: { core: 1 },
        state_counts: { RUNNING: 1 },
        agents: [agent],
      });
    }

    if (pathname === "/v1/operations/agent-integrations" && request.method() === "GET") {
      return fulfillJson(route, 200, {
        generated_at: new Date().toISOString(),
        total_agents: 1,
        persona_profile_framework: "8-part",
        persona_profile_sections: [
          "job_role",
          "education_certifications",
          "traits_skills",
          "methods_procedures",
          "tools",
          "master_instruction",
          "protocol",
          "api_configuration",
        ],
        llm_strategy_version: "2026-03-03",
        llm_provider_counts: { openai: 1 },
        llm_model_counts: { "gpt-4.1": 1 },
        agents: [
          {
            agent_id: "AGENT-01-PM",
            name: "Agent One PM",
            short_code: "PM",
            tier: "manager",
            pod: "core",
            llm_recommendation: { provider: "openai", model: "gpt-4.1" },
            persona_profile: personaProfile("AGENT-01-PM"),
          },
        ],
      });
    }

    if (pathname === "/v1/operations/logicnodes" && request.method() === "GET") {
      const missionId = url.searchParams.get("mission_id") ?? missions[0]?.mission_id ?? seedMissionId;
      return fulfillJson(route, 200, missionLogicNodes.get(missionId) ?? []);
    }

    if (pathname === "/v1/builder/preview" && request.method() === "POST") {
      return fulfillJson(route, 200, {
        request_id: "preview-001",
        source: "e2e",
        generated_at: new Date().toISOString(),
        plan: [{ title: "Scope", description: "Drafted mission scope from user intent." }],
        diff_summary: ["No source diff generated in mock mode."],
        risk_notes: [],
        test_plan: ["Run regression checks"],
      });
    }

    if (pathname === "/health" && request.method() === "GET") {
      return fulfillJson(route, 200, {
        ok: true,
        service: "api-gateway",
        orchestrator_url: "http://orchestrator:8001",
        orchestrator_healthy: true,
        redis_url: "redis://redis:6379/0",
        redis_healthy: true,
        intake_stream: "missions.intake",
        intake_topic: "intake.feature_contract.created",
      });
    }

    if (pathname === "/readyz" && request.method() === "GET") {
      return fulfillJson(route, 200, { ready: true });
    }

    return fulfillJson(route, 404, {
      detail: `No mock route configured for ${request.method()} ${pathname}`,
    });
  });
}

test("mission lifecycle journey is covered from intake to live detail", async ({ page }) => {
  await setupMissionControlApiMocks(page);

  await page.goto("/missions");
  await expect(page.getByRole("heading", { name: "Mission Intake and Lifecycle" })).toBeVisible();

  await page.getByLabel("Mission prompt").fill("Build payroll reconciliation API with retry-safe updates.");
  await page.getByRole("button", { name: "Launch Mission" }).click();

  await expect(page.getByText(/accepted and queued/i)).toBeVisible();
  await page.getByRole("link", { name: "View Live" }).first().click();

  await expect(page).toHaveURL(/\/missions\/mission-e2e-\d+/);
  await expect(page.getByRole("heading", { name: /Mission mission-e2e-/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Smelt-Cycle Phase Stepper" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mission Event Log" })).toBeVisible();
});

test("operations views render runtime and agent persona detail", async ({ page }) => {
  await setupMissionControlApiMocks(page);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Launch Pad" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Runtime Health" })).toBeVisible();
  await expect(page.getByText("Gateway readiness")).toBeVisible();

  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "35-Agent Runtime Control Grid" })).toBeVisible();
  await expect(page.getByText("Total agents")).toBeVisible();
  await expect(page.getByText(/Windowed rows:/i)).toBeVisible();
  await page.getByRole("button", { name: /Agent One PM/i }).first().click();
  await expect(page.getByRole("heading", { name: /Agent Detail - AGENT-01-PM/i })).toBeVisible();
  await expect(page.getByText(/log entries \(windowed\)/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: "8-Part Persona Profile" })).toBeVisible();
});

test("settings and vault flows are regression covered", async ({ page }) => {
  await setupMissionControlApiMocks(page);

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Local Runtime and Integrations" })).toBeVisible();

  const slotRow = page.locator("tr", { hasText: "AGENT-01-PM-API-KEY" });
  await slotRow.getByRole("button", { name: "Select" }).click();

  await page.getByLabel("Secret").fill("sk-ant-e2e-secret-123456");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText(/Saved AGENT-01-PM-API-KEY\./)).toBeVisible();

  await page.getByRole("button", { name: "Test" }).click();
  await expect(page.getByText(/Valid:/)).toBeVisible();

  await page.getByRole("button", { name: "Clear" }).click();
  await expect(page.getByText(/Cleared AGENT-01-PM-API-KEY\./)).toBeVisible();

  await page.getByLabel("API base URL").fill("https://example.com");
  await page.getByRole("button", { name: "Save Runtime Preferences" }).click();
  await expect(page.getByText(/must target localhost or 127.0.0.1/i)).toBeVisible();

  await page.getByLabel("API base URL").fill("http://localhost:8100");
  await page.getByRole("button", { name: "Save Runtime Preferences" }).click();
  await expect(page.getByText("Local runtime preferences saved.")).toBeVisible();
});

test("builder workspace generates actionable diff previews", async ({ page }) => {
  await setupMissionControlApiMocks(page);

  await page.goto("/builder");
  await expect(page.getByRole("heading", { name: "Builder Workspace" })).toBeVisible();

  await page
    .getByLabel("Change request")
    .fill("Update builder workflow to include stronger risk notes and test guidance.");
  await page.getByLabel("Constraints (comma-separated)").fill("no schema changes, preserve accessibility");
  await page.getByRole("button", { name: "Stage Request" }).click();

  await expect(page.getByText(/Preview generated from e2e/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Execution Plan" })).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "apps/mission-control/app/(shell)/builder/page.tsx",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.locator(".code-block pre").first()).toContainText("+    request:");
});

test("repo intake imports files and launches mission", async ({ page }) => {
  await setupMissionControlApiMocks(page);

  await page.goto("/repo");
  await expect(
    page.getByRole("heading", { name: "Repository Intake and Mission Configuration" }),
  ).toBeVisible();

  await page.getByLabel("GitHub repository URL").fill("https://github.com/octo/sample-platform");
  await page.getByRole("button", { name: "Import Repository" }).click();

  await expect(page.getByText("octo/sample-platform", { exact: true })).toBeVisible();
  await expect(page.getByText("Selected 3 files from /.")).toBeVisible();

  await page.getByRole("button", { name: "Select Top 25" }).click();
  await expect(page.getByText(/Selected: 3 files - 510 estimated lines/)).toBeVisible();

  await page.getByRole("button", { name: "Generate Diff Review" }).click();
  await expect(page.getByRole("heading", { name: "Diff Summary" })).toBeVisible();
  await page.getByRole("button", { name: "Apply Review Gate" }).click();
  await expect(page.getByText(/Review gate applied at/i)).toBeVisible();

  await page.getByRole("button", { name: "Analyze" }).click();
  await page.getByRole("button", { name: "Launch Mission" }).click();

  await expect(page).toHaveURL(/\/missions\/mission-e2e-\d+/);
  await expect(page.getByRole("heading", { name: /Mission mission-e2e-/i })).toBeVisible();
});

test("error states surface actionable UI messaging", async ({ page }) => {
  await setupMissionControlApiMocks(page, {
    failMissionList: true,
    failMissionCreate: true,
  });

  await page.goto("/missions");
  await expect(page.locator(".error-box", { hasText: "Mission list unavailable for test." })).toBeVisible();

  await page.getByLabel("Mission prompt").fill("Trigger a mission submit error path.");
  await page.getByRole("button", { name: "Launch Mission" }).click();
  await expect(
    page.locator(".error-box", { hasText: /Review mission prompt and retry\./ }),
  ).toBeVisible();
});

test("accessibility checks pass on mission flow pages", async ({ page }) => {
  await setupMissionControlApiMocks(page);

  await page.goto("/missions");
  await expect(page.getByRole("heading", { name: "Mission Intake and Lifecycle" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(".skip-link")).toBeFocused();

  const missionsA11y = await new AxeBuilder({ page })
    .disableRules(["color-contrast"])
    .analyze();
  expect(missionsA11y.violations).toEqual([]);

  await page.getByRole("link", { name: "View Live" }).first().click();
  await expect(page.getByRole("heading", { name: /Mission mission-seed-001/i })).toBeVisible();

  const detailA11y = await new AxeBuilder({ page })
    .disableRules(["color-contrast"])
    .analyze();
  expect(detailA11y.violations).toEqual([]);
});
