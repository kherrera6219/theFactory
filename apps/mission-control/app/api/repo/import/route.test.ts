import { describe, expect, it } from "vitest";

import {
  languageFromPath,
  POST,
  normalizeSubdirectory,
  parseGithubRepoUrl,
  selectRepoFiles,
} from "./route";

describe("repo import route helpers", () => {
  it("parses canonical github urls and trims .git suffix", () => {
    expect(parseGithubRepoUrl("https://github.com/org/repo")).toEqual({
      owner: "org",
      repo: "repo",
    });
    expect(parseGithubRepoUrl("https://github.com/org/repo.git")).toEqual({
      owner: "org",
      repo: "repo",
    });
    expect(parseGithubRepoUrl("https://github.com/org/repo/tree/main")).toEqual({
      owner: "org",
      repo: "repo",
    });
  });

  it("rejects unsupported repository urls", () => {
    expect(parseGithubRepoUrl("http://github.com/org/repo")).toBeNull();
    expect(parseGithubRepoUrl("https://gitlab.com/org/repo")).toBeNull();
    expect(parseGithubRepoUrl("https://github.com/org")).toBeNull();
    expect(parseGithubRepoUrl("not-a-url")).toBeNull();
  });

  it("normalizes subdirectory values", () => {
    expect(normalizeSubdirectory("")).toBe("/");
    expect(normalizeSubdirectory("/")).toBe("/");
    expect(normalizeSubdirectory("src")).toBe("/src");
    expect(normalizeSubdirectory("/src/lib/")).toBe("/src/lib");
  });

  it("maps known extensions to languages", () => {
    expect(languageFromPath("service/main.py")).toBe("Python");
    expect(languageFromPath("web/App.TSX")).toBe("TypeScript");
    expect(languageFromPath("docs/README.md")).toBe("Markdown");
    expect(languageFromPath("assets/logo.svg")).toBe("Other");
  });

  it("filters, sorts, and truncates repository files", () => {
    const selection = selectRepoFiles(
      [
        { type: "tree", path: "services" },
        { type: "blob", path: "services/api/main.py", size: 9000 },
        { type: "blob", path: "services/api/router.py", size: 1000 },
        { type: "blob", path: "services/api/huge.bin", size: 2_000_000 },
        { type: "blob", path: "web/app/page.tsx", size: 3000 },
      ],
      "/services",
      1,
    );

    expect(selection.files).toHaveLength(1);
    expect(selection.files[0]).toMatchObject({
      path: "services/api/main.py",
      language: "Python",
      bytes: 9000,
    });
    expect(selection.skippedLargeFiles).toBe(1);
    expect(selection.truncated).toBe(true);
  });

  it("includes root files when subdirectory is slash", () => {
    const selection = selectRepoFiles(
      [
        { type: "blob", path: "README.md", size: 500 },
        { type: "blob", path: "apps/mission-control/app.tsx", size: 1500 },
      ],
      "/",
      10,
    );

    expect(selection.files.map((file) => file.path)).toEqual([
      "apps/mission-control/app.tsx",
      "README.md",
    ]);
    expect(selection.truncated).toBe(false);
    expect(selection.skippedLargeFiles).toBe(0);
  });

  it("rejects repository intake without an operator session", async () => {
    const response = await POST(
      new Request("http://localhost/api/repo/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: "https://github.com/octo/sample-platform",
          branch: "main",
          subdirectory: "/",
          max_files: 10,
        }),
      }),
    );

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toMatchObject({
      detail: expect.stringContaining("operator session"),
    });
  });
});
