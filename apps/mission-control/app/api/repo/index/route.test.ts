import { afterEach, describe, expect, it, vi } from "vitest";

const ORIGINAL_BYPASS = process.env.MISSION_CONTROL_BYPASS_AUTH;
const ORIGINAL_INTERNAL_KEY = process.env.INTERNAL_SERVICE_API_KEY;
const ORIGINAL_BASE_URL = process.env.ORCHESTRATOR_INTERNAL_BASE_URL;

function request(body: unknown): Request {
  return new Request("http://localhost/api/repo/index", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("repo index route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.resetModules();
    if (ORIGINAL_BYPASS === undefined) {
      delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    } else {
      process.env.MISSION_CONTROL_BYPASS_AUTH = ORIGINAL_BYPASS;
    }
    if (ORIGINAL_INTERNAL_KEY === undefined) {
      delete process.env.INTERNAL_SERVICE_API_KEY;
    } else {
      process.env.INTERNAL_SERVICE_API_KEY = ORIGINAL_INTERNAL_KEY;
    }
    if (ORIGINAL_BASE_URL === undefined) {
      delete process.env.ORCHESTRATOR_INTERNAL_BASE_URL;
    } else {
      process.env.ORCHESTRATOR_INTERNAL_BASE_URL = ORIGINAL_BASE_URL;
    }
  });

  it("builds bounded manifest/summary/chunk records and posts them to the orchestrator", async () => {
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
    process.env.INTERNAL_SERVICE_API_KEY = "internal-test-key";
    process.env.ORCHESTRATOR_INTERNAL_BASE_URL = "http://orchestrator:8101";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ index_status: "complete", indexed_knowledge_count: 4 }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./route");

    const response = await POST(
      request({
        mission_id: "mission-1",
        import_id: "repozip-abc123",
        archive_sha256: "sha-abc",
        display_name: "sample-platform",
        source_ref: "main",
        files: [
          {
            path: "src/index.ts",
            language: "TypeScript",
            content_excerpt: "export const x = 1;",
            bytes: 20,
            estimated_lines: 1,
            sha: "file-sha-1",
            overlay_action: "include",
          },
        ],
      }),
    );

    expect(response.status).toBe(200);
    const payload = (await response.json()) as { index_status?: string };
    expect(payload.index_status).toBe("complete");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://orchestrator:8101/internal/missions/mission-1/repo-import-index");
    expect(init.headers["x-api-key"]).toBe("internal-test-key");
    const sentBody = JSON.parse(init.body as string) as {
      import_manifest: { knowledge_id: string; kind: string };
      summary_record: { knowledge_id: string; kind: string };
      chunk_records: Array<{ knowledge_id: string; path: string }>;
    };
    expect(sentBody.import_manifest.knowledge_id).toBe("repo.repozip-abc123.manifest");
    expect(sentBody.import_manifest.kind).toBe("repo_manifest");
    expect(sentBody.summary_record.knowledge_id).toBe("repo.repozip-abc123.summary");
    expect(sentBody.chunk_records).toHaveLength(1);
    expect(sentBody.chunk_records[0].path).toBe("src/index.ts");
    expect(sentBody.chunk_records[0].knowledge_id).toMatch(/^repo\.repozip-abc123\.file\.[0-9a-f]{16}\.chunk\.0$/);
  });

  it("returns 400 when mission_id is missing", async () => {
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
    process.env.INTERNAL_SERVICE_API_KEY = "internal-test-key";
    const { POST } = await import("./route");

    const response = await POST(request({ import_id: "repozip-abc123", files: [] }));

    expect(response.status).toBe(400);
  });

  it("returns 400 when INTERNAL_SERVICE_API_KEY is not configured", async () => {
    process.env.MISSION_CONTROL_BYPASS_AUTH = "true";
    delete process.env.INTERNAL_SERVICE_API_KEY;
    const { POST } = await import("./route");

    const response = await POST(
      request({ mission_id: "mission-1", import_id: "repozip-abc123", files: [] }),
    );

    expect(response.status).toBe(400);
  });

  it("rejects requests without an operator session", async () => {
    delete process.env.MISSION_CONTROL_BYPASS_AUTH;
    // Session mechanism left fully unconfigured (no secret/admin key) --
    // requireOperatorRequestSession reports 503 in this state, matching the
    // rest of this app's privileged routes (e.g. the gateway proxy).
    delete process.env.MISSION_CONTROL_SESSION_SECRET;
    delete process.env.MISSION_CONTROL_ADMIN_KEY;
    const { POST } = await import("./route");

    const response = await POST(
      request({ mission_id: "mission-1", import_id: "repozip-abc123", files: [] }),
    );

    expect(response.status).toBe(503);
  });
});
