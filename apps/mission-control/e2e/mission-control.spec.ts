import { expect, test, type Page, type Route } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

import { attachOperatorSession } from "./test-helpers";

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
        model: "gpt-5.5",
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

function gatewayPathname(url: URL): string {
  return url.pathname.replace(/^\/api\/gateway(?=\/|$)/, "");
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

  await page.route("**/api/repo/review", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      return fulfillJson(route, 405, { detail: "Method not allowed." });
    }
    const payload = (request.postDataJSON() as Record<string, unknown>) ?? {};
    const selectedFiles = Array.isArray(payload.selected_files)
      ? (payload.selected_files as Array<Record<string, unknown>>)
      : [];
    if (selectedFiles.length === 0) {
      return fulfillJson(route, 400, { detail: "Select files before review." });
    }

    return fulfillJson(route, 200, {
      request_id: "repo-review-001",
      review_fingerprint: "fp-repo-review-001",
      source: "repo-review",
      generated_at: new Date().toISOString(),
      repository: {
        owner: "octo",
        repo: "sample-platform",
        branch: "main",
        html_url: "https://github.com/octo/sample-platform",
        selected_subdirectory: "/",
      },
      mission_type: typeof payload.mission_type === "string" ? payload.mission_type : "analyze",
      requested_target_language: "typescript",
      source_code:
        "# Repository Source Bundle\nrepository: octo/sample-platform\nbranch: main\n\n## FILE apps/mission-control/app/(shell)/repo/page.tsx\nexport default function RepoPage() {}\n",
      source_stats: {
        selected_files: selectedFiles.length,
        include_files: selectedFiles.filter((item) => item.overlay_action === "include").length,
        reference_files: selectedFiles.filter((item) => item.overlay_action === "reference").length,
        source_characters: 164,
        bundled_files: selectedFiles.length,
        truncated_files: 0,
        unavailable_files: 0,
      },
      plan: [
        { title: "Lock Approved Scope", description: "Review fetched repository content before launch." },
        { title: "Edit Direct Files", description: "Direct-edit scope is apps/mission-control/app/(shell)/repo/page.tsx." },
      ],
      diff_summary: [
        "Reviewed 3 selected files from octo/sample-platform@main.",
        "Direct-edit scope covers 3 files; 0 files remain reference-only.",
        "Primary target language resolved to typescript.",
      ],
      risk_notes: ["API-facing files are in scope; preserve request/response contracts and error handling."],
      test_plan: ["Run Mission Control TypeScript and Vitest coverage for the touched UI and route logic."],
      files: [
        {
          path: "apps/mission-control/app/(shell)/repo/page.tsx",
          overlay_action: "include",
          language: "TypeScript",
          requested_language: "typescript",
          bytes: 12_000,
          estimated_lines: 260,
          summary: "Client TypeScript component focused on repository review and mission launch.",
          content_excerpt: "\"use client\";\n\nexport default function RepoPage() {}",
          text_available: true,
          included_in_source: true,
          truncated_in_source: false,
          sha: "sha-repo-page",
        },
        {
          path: "services/api-gateway/api_gateway/main.py",
          overlay_action: "include",
          language: "Python",
          requested_language: "python",
          bytes: 9_400,
          estimated_lines: 210,
          summary: "Python service module handling API flow and orchestration.",
          content_excerpt: "from fastapi import FastAPI",
          text_available: true,
          included_in_source: true,
          truncated_in_source: false,
          sha: "sha-api-main",
        },
        {
          path: "README.md",
          overlay_action: "include",
          language: "Markdown",
          requested_language: null,
          bytes: 1_800,
          estimated_lines: 40,
          summary: "Documentation file covering repository context and operator guidance.",
          content_excerpt: "# Sample Platform",
          text_available: true,
          included_in_source: true,
          truncated_in_source: false,
          sha: "sha-readme",
        },
      ],
    });
  });

  await page.route("**/api/builder/review", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      return fulfillJson(route, 405, { detail: "Method not allowed." });
    }
    return fulfillJson(route, 200, {
      request_id: "builder-review-001",
      source: "workspace-review",
      generated_at: new Date().toISOString(),
      builder_fingerprint: "fp-builder-review-001",
      requested_target_language: "typescript",
      source_code:
        "# Builder Workspace Source Bundle\nbuilder_fingerprint: fp-builder-review-001\nrequested_target_language: typescript\n",
      patch_text:
        "diff --git a/apps/mission-control/app/(shell)/builder/page.tsx b/apps/mission-control/app/(shell)/builder/page.tsx\n--- a/apps/mission-control/app/(shell)/builder/page.tsx\n+++ b/apps/mission-control/app/(shell)/builder/page.tsx\n@@ -1,1 +1,2 @@\n \"use client\";\n+// builder-intent: Update builder workflow to include stronger risk notes and test guidance.\n",
      source_stats: {
        selected_files: 2,
        source_characters: 512,
        patch_characters: 287,
        high_risk_files: 1,
      },
      plan: [
        { title: "Ground Real Files", description: "Review uses local repository files rather than client-side file hints." },
        { title: "Generate Patch Contract", description: "Prepared a patch contract for 2 files using the current workspace state." },
        { title: "Launch With Approved Bundle", description: "Use the generated source bundle and approval receipt when creating the mission." },
      ],
      diff_summary: [
        "apps/mission-control/app/(shell)/builder/page.tsx: Modify builder page around grounded UI state.",
        "services/api-gateway/api_gateway/main.py: Modify Python flow around create_builder_preview.",
      ],
      risk_notes: ["services/api-gateway/api_gateway/main.py is high-risk and needs focused validation."],
      test_plan: ["Validate the grounded file selection before approval."],
      notice: "Builder review now returns a grounded patch contract and launch bundle; approval is still required before mission execution.",
      files: [
        {
          path: "apps/mission-control/app/(shell)/builder/page.tsx",
          operation: "modify",
          risk: "low",
          summary: "Modify builder page around grounded UI state.",
          excerpt: "\"use client\";\nexport default function BuilderPage() {",
          lines: [
            { kind: "context", value: "@@ grounded preview @@" },
            { kind: "context", value: "\"use client\";" },
            { kind: "remove", value: "export default function BuilderPage() {" },
            { kind: "add", value: "// staged builder change: Update builder workflow to include stronger risk notes and test guidance." },
            { kind: "add", value: "export default function BuilderPage() {" },
          ],
        },
        {
          path: "services/api-gateway/api_gateway/main.py",
          operation: "modify",
          risk: "high",
          summary: "Modify Python flow around create_builder_preview.",
          excerpt: "async def create_builder_preview(payload):",
          lines: [
            { kind: "context", value: "@@ grounded preview @@" },
            { kind: "context", value: "async def create_builder_preview(payload):" },
            { kind: "remove", value: "    return existing_preview(payload)" },
            { kind: "add", value: "# staged builder change: Update builder workflow to include stronger risk notes and test guidance." },
            { kind: "add", value: "    return existing_preview(payload)" },
          ],
        },
      ],
    });
  });

  await page.route("**/api/review/approve", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      return fulfillJson(route, 405, { detail: "Method not allowed." });
    }
    const payload = (request.postDataJSON() as Record<string, unknown>) ?? {};
    const scope = typeof payload.scope === "string" ? payload.scope : "repo";
    const fingerprint = typeof payload.fingerprint === "string" ? payload.fingerprint : "fp-default";

    return fulfillJson(route, 200, {
      approval_id: `${scope}-approval-001`,
      scope,
      fingerprint,
      approved_at: new Date().toISOString(),
      summary: typeof payload.summary === "string" ? payload.summary : "Review approved.",
      receipt_digest: `${scope}-digest-001`,
      record_path: `orchestrator://review-approvals/${scope}-approval-001`,
    });
  });

  await page.route("**/api/review/verify", async (route) => {
    const request = route.request();
    if (request.method() !== "POST") {
      return fulfillJson(route, 405, { detail: "Method not allowed." });
    }
    const payload = (request.postDataJSON() as Record<string, unknown>) ?? {};
    const scope = typeof payload.scope === "string" ? payload.scope : "repo";
    const fingerprint = typeof payload.fingerprint === "string" ? payload.fingerprint : "fp-default";

    return fulfillJson(route, 200, {
      scope,
      approval_id:
        typeof payload.approval_id === "string"
          ? payload.approval_id
          : `${scope}-approval-001`,
      fingerprint,
      receipt_digest:
        typeof payload.receipt_digest === "string"
          ? payload.receipt_digest
          : `${scope}-digest-001`,
      verified: true,
      verified_at: new Date().toISOString(),
    });
  });

  await page.route(/(?:http:\/\/(?:localhost|127\.0\.0\.1):8100\/.*|.*\/api\/gateway\/.*)/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const pathname = gatewayPathname(url);

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

    const missionChainTraceMatch = pathname.match(/^\/v1\/missions\/([^/]+)\/chain-trace$/);
    if (missionChainTraceMatch && request.method() === "GET") {
      const missionId = decodeURIComponent(missionChainTraceMatch[1]);
      return fulfillJson(route, 200, {
        mission_id: missionId,
        routing_enforced: true,
        routing_version: "v2",
        selected_agent_id: "AGENT-14-PYTHON",
        intake_agent_id: "AGENT-01-PM",
        executive_agent_id: "AGENT-02-CEO",
        assigned_pod_manager_agent_id: "AGENT-12-PODA-MGR",
        assigned_specialist_agent_id: "AGENT-14-PYTHON",
        pod_assignment: { mission_id: missionId, pod_name: "podA" },
        logicnode_count: 1,
        artifact_summary: {
          pm_intake: {
            event_type: "MISSION_PM_INTAKE",
            agent_id: "AGENT-01-PM",
            recorded_at: "2026-03-03T11:59:05.000Z",
          },
          ceo_delegated: {
            event_type: "MISSION_CEO_DELEGATED",
            agent_id: "AGENT-02-CEO",
            recorded_at: "2026-03-03T11:59:10.000Z",
          },
          specialist_planned: {
            event_type: "MISSION_SPECIALIST_PLANNED",
            agent_id: "AGENT-14-PYTHON",
            recorded_at: "2026-03-03T11:59:20.000Z",
          },
        },
        route_provenance: {
          ceo: {
            role: "ceo",
            source: "llm",
            llm_route: "primary",
            model_provider: "openai",
            model: "gpt-5.5",
            target_agent_id: "AGENT-12-PODA-MGR",
            specialist_agent_id: "AGENT-14-PYTHON",
            rationale: "Python work routes through Pod A.",
          },
          pod_manager: {
            role: "pod_manager",
            source: "llm",
            llm_route: "primary",
            model_provider: "openai",
            model: "gpt-5.5",
            target_agent_id: "AGENT-14-PYTHON",
            pod_manager_agent_id: "AGENT-12-PODA-MGR",
            rationale: "Pod A manager confirmed Python specialist.",
          },
          specialist: {
            role: "specialist",
            source: "fallback",
            llm_route: "fallback",
            model_provider: "openai",
            model: "gpt-5.5",
            specialist_agent_id: "AGENT-14-PYTHON",
            pod_manager_agent_id: "AGENT-12-PODA-MGR",
            plan_summary: "Implement the requested change and publish logicnode evidence.",
            deliverables: ["Implementation patch", "LogicNode evidence"],
            risk_notes: ["Fallback route used for deterministic planning."],
          },
          fallback_used: true,
        },
        events: [
          {
            event_type: "MISSION_PM_INTAKE",
            agent_id: "AGENT-01-PM",
            ts: "2026-03-03T11:59:05.000Z",
          },
          {
            event_type: "MISSION_CEO_DELEGATED",
            agent_id: "AGENT-02-CEO",
            ts: "2026-03-03T11:59:10.000Z",
          },
          {
            event_type: "MISSION_SPECIALIST_PLANNED",
            agent_id: "AGENT-14-PYTHON",
            ts: "2026-03-03T11:59:20.000Z",
          },
        ],
      });
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
        runtime_class: "shared_worker",
        heartbeat_source: "live",
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
        llm_model_counts: { "gpt-5.5": 1 },
        agents: [
          {
            agent_id: "AGENT-01-PM",
            name: "Agent One PM",
            short_code: "PM",
            tier: "manager",
            pod: "core",
            llm_recommendation: { provider: "openai", model: "gpt-5.5" },
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

test.beforeEach(async ({ page }) => {
  await attachOperatorSession(page);
});

test("mission lifecycle journey is covered from intake to live detail", async ({ page }) => {
  await setupMissionControlApiMocks(page);

  await page.goto("/missions");
  await expect(page.getByRole("heading", { name: "Mission Intake and Lifecycle" })).toBeVisible();

  await page.getByLabel("Mission prompt").fill("Build payroll reconciliation API with retry-safe updates.");
  await page.getByRole("button", { name: "Launch Mission" }).click();

  await expect(page.getByText(/accepted and queued/i)).toBeVisible();
  await page.getByRole("link", { name: "View Live" }).first().click();

  await expect(page).toHaveURL(/\/missions\/detail\?id=mission-e2e-\d+/);
  await expect(page.getByRole("heading", { name: /Mission mission-e2e-/i })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Mission Phase Stepper" })).toBeVisible();

  // Phase 2B tabbed layout: Route Provenance + CEO Delegation live in the
  // Contracts tab, and the Mission Event Log lives in the Events tab. Panels in
  // inactive tabs are `hidden` and excluded from the accessibility tree.
  await page.getByRole("tab", { name: "Contracts" }).click();
  await expect(page.getByRole("heading", { name: "Route Provenance" })).toBeVisible();
  await expect(page.getByText("CEO Delegation")).toBeVisible();

  await page.getByRole("tab", { name: "Events" }).click();
  await expect(page.getByRole("heading", { name: "Mission Event Log" })).toBeVisible();
});

test("operations views render runtime and agent persona detail", async ({ page }) => {
  await setupMissionControlApiMocks(page);

  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Launch Pad" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Runtime Health" })).toBeVisible();
  await expect(page.getByText("Gateway readiness")).toBeVisible();

  await page.goto("/agents");
  await expect(page.getByRole("heading", { name: "Agent Runtime Control Grid" })).toBeVisible();
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
  await slotRow.getByRole("button", { name: "Configure" }).click();

  await page.getByLabel("Secret").fill("sk-ant-e2e-secret-123456");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText(/Saved AGENT-01-PM-API-KEY\./)).toBeVisible();

  await page.getByRole("button", { name: "Test" }).click();
  await expect(page.getByText(/Valid:/)).toBeVisible();

  await page.getByRole("button", { name: "Clear" }).click();
  await expect(page.getByText(/Cleared AGENT-01-PM-API-KEY\./)).toBeVisible();

  await page.getByLabel("API base URL").fill("https://example.com");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText(/must target localhost or 127.0.0.1/i)).toBeVisible();

  await page.getByLabel("API base URL").fill("http://localhost:8100");
  await page.getByRole("button", { name: "Save preferences" }).click();
  await expect(page.getByText("Preferences saved.")).toBeVisible();
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

  await expect(page.getByText(/Preview generated from workspace-review/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Execution Plan" })).toBeVisible();
  await expect(
    page.getByRole("heading", {
      name: "apps/mission-control/app/(shell)/builder/page.tsx",
      exact: true,
    }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "Step 2: Review Patch Contract" })).toBeVisible();
  await expect(page.locator(".code-block pre").last()).toContainText("diff --git a/apps/mission-control/app/(shell)/builder/page.tsx");
  await page.getByRole("button", { name: "Apply Review Gate" }).click();
  await expect(page.getByText(/Review gate persisted at/i)).toBeVisible();
  await page.getByRole("button", { name: "Launch Mission" }).click();
  await expect(page).toHaveURL(/\/missions\/detail\?id=mission-e2e-\d+/);
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

  await page.getByRole("button", { name: "Analyze" }).click();
  await page.getByRole("button", { name: "Generate Repository Review" }).click();
  await expect(page.getByRole("heading", { name: "Review Summary" })).toBeVisible();
  await page.getByRole("button", { name: "Apply Review Gate" }).click();
  await expect(page.getByText(/Review gate persisted at/i)).toBeVisible();

  await expect(page.getByText("Requested target language")).toBeVisible();
  await page.getByRole("button", { name: "Launch Mission" }).click();

  await expect(page).toHaveURL(/\/missions\/detail\?id=mission-e2e-\d+/);
  await expect(page.getByRole("heading", { name: /Mission mission-e2e-/i })).toBeVisible();
});

test("error states surface actionable UI messaging", async ({ page }) => {
  await setupMissionControlApiMocks(page, {
    failMissionList: true,
    failMissionCreate: true,
  });

  await page.goto("/missions");
  await expect(page.getByText("Mission list unavailable for test.").first()).toBeVisible();

  await page.getByLabel("Mission prompt").fill("Trigger a mission submit error path.");
  await page.getByRole("button", { name: "Launch Mission" }).click();
  await expect(page.getByText(/Review mission prompt and retry\./).first()).toBeVisible();
});

test("accessibility checks pass on mission flow pages", async ({ page }) => {
  await setupMissionControlApiMocks(page);

  await page.goto("/missions");
  await expect(page.getByRole("heading", { name: "Mission Intake and Lifecycle" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(".skip-link")).toBeFocused();

  const missionsA11y = await new AxeBuilder({ page }).analyze();
  expect(missionsA11y.violations).toEqual([]);

  const liveMissionLink = page.getByRole("link", { name: "View Live" }).first();
  await expect(liveMissionLink).toBeVisible();
  const liveMissionHref = await liveMissionLink.getAttribute("href");
  await liveMissionLink.click();
  if (liveMissionHref) {
    // Escape all regex metacharacters (the href now contains "?" and "=").
    const escapedHref = liveMissionHref.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    await expect(page).toHaveURL(new RegExp(`${escapedHref}$`));
  } else {
    await expect(page).toHaveURL(/\/missions\/[^/]+$/);
  }
  await expect(page.getByRole("heading", { name: /^Mission mission-/i })).toBeVisible();

  const detailA11y = await new AxeBuilder({ page }).analyze();
  expect(detailA11y.violations).toEqual([]);
});
