import { afterEach, describe, expect, it, vi } from "vitest";

describe("review approval route", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.resetModules();
    delete process.env.INTERNAL_SERVICE_API_KEY;
    delete process.env.ORCHESTRATOR_INTERNAL_BASE_URL;
  });

  it("persists an approval receipt through orchestrator storage", async () => {
    process.env.INTERNAL_SERVICE_API_KEY = "internal-test-key";
    process.env.ORCHESTRATOR_INTERNAL_BASE_URL = "http://orchestrator:8001";
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          approval_id: "repo-approval-f1234567890abcde",
          scope: "repo",
          fingerprint: "f1234567890abcdef",
          approved_at: "2026-03-29T00:00:00+00:00",
          summary: "Repository review approved for mission launch.",
          metadata: { request_id: "repo-review-001" },
          receipt_digest: "digest-001",
          storage_backend: "postgres",
          record_path: "orchestrator://review-approvals/repo-approval-f1234567890abcde",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://localhost/api/review/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scope: "repo",
          fingerprint: "f1234567890abcdef",
          summary: "Repository review approved for mission launch.",
          metadata: { request_id: "repo-review-001" },
        }),
      }),
    );

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://orchestrator:8001/internal/review-approvals",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "Content-Type": "application/json",
          "x-api-key": "internal-test-key",
        }),
        cache: "no-store",
      }),
    );

    const payload = (await response.json()) as Record<string, string>;
    expect(payload.approval_id).toContain("repo-approval-");
    expect(payload.record_path).toBe(
      "orchestrator://review-approvals/repo-approval-f1234567890abcde",
    );
    expect(payload.storage_backend).toBe("postgres");
  });

  it("fails closed when the internal service key is missing", async () => {
    const { POST } = await import("./route");

    const response = await POST(
      new Request("http://localhost/api/review/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          scope: "builder",
          fingerprint: "builder-fingerprint-1234",
          summary: "Approve builder launch.",
        }),
      }),
    );

    expect(response.status).toBe(503);
    const payload = (await response.json()) as { detail?: string };
    expect(payload.detail).toMatch(/INTERNAL_SERVICE_API_KEY/i);
  });
});
