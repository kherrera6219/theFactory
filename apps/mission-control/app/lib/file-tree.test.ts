import { describe, expect, it } from "vitest";
import { computeLineDiff, parseMultiFileBundle, sanitizeVirtualPath } from "./file-tree";

describe("file-tree multi-file bundle parser and diff engine (Phase 6)", () => {
  it("parses ## FILE and ## FILE: bundles into individual VirtualFileEntry items", () => {
    const bundle = [
      "## FILE src/index.ts",
      "export const x = 1;",
      "",
      "## FILE: tests/index.test.ts",
      "import { x } from '../src/index';",
      "console.log(x);",
    ].join("\n");

    const files = parseMultiFileBundle(bundle, "bundle.ts", "typescript");
    expect(files).toHaveLength(2);
    expect(files[0]?.path).toBe("src/index.ts");
    expect(files[0]?.directory).toBe("src");
    expect(files[0]?.name).toBe("index.ts");
    expect(files[0]?.language).toBe("typescript");
    expect(files[0]?.content).toContain("export const x = 1;");
    expect(files[1]?.path).toBe("tests/index.test.ts");
    expect(files[1]?.lineCount).toBe(2);
  });

  it("returns a single VirtualFileEntry when no ## FILE markers exist", () => {
    const files = parseMultiFileBundle("print('hello')\n", "app.py", "python");
    expect(files).toHaveLength(1);
    expect(files[0]?.path).toBe("app.py");
    expect(files[0]?.language).toBe("python");
  });

  it("sanitizes path traversal attempts", () => {
    expect(sanitizeVirtualPath("../../etc/passwd")).toBe("etc/passwd");
    expect(sanitizeVirtualPath("C:\\src\\main.py")).toBe("src/main.py");
  });

  it("computes line-by-line LCS diff for brownfield comparisons", () => {
    const before = "line 1\nold line 2\nline 3";
    const after = "line 1\nnew line 2\nline 3";
    const diff = computeLineDiff(before, after);
    expect(diff.map((d) => d.type)).toEqual(["same", "del", "add", "same"]);
  });
});
