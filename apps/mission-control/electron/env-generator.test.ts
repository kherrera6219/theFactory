import fs from "fs";
import os from "os";
import path from "path";
import { afterEach, describe, expect, it } from "vitest";
import { upsertEnvValues } from "./env-generator";

const dirs: string[] = [];
function tempEnv(content: string): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "hgr-env-"));
  dirs.push(dir);
  const file = path.join(dir, "backend.env");
  fs.writeFileSync(file, content);
  return file;
}
afterEach(() => dirs.splice(0).forEach((d) => fs.rmSync(d, { recursive: true, force: true })));

describe("upsertEnvValues", () => {
  it("replaces existing keys, appends new ones, and leaves secrets untouched", () => {
    const file = tempEnv("# header\nPOSTGRES_PASSWORD=s3cret\nFACTORY_IMAGE_TAG=v1.0.0\n");
    upsertEnvValues(file, { FACTORY_IMAGE_TAG: "v1.1.0", SANDBOX_WORKSPACE_HOST_ROOT: "C:/data/ws" });
    expect(fs.readFileSync(file, "utf-8")).toBe(
      "# header\nPOSTGRES_PASSWORD=s3cret\nFACTORY_IMAGE_TAG=v1.1.0\nSANDBOX_WORKSPACE_HOST_ROOT=C:/data/ws\n",
    );
  });

  it("preserves CRLF files", () => {
    const file = tempEnv("A=1\r\nB=2\r\n");
    upsertEnvValues(file, { B: "3" });
    expect(fs.readFileSync(file, "utf-8")).toBe("A=1\r\nB=3\r\n");
  });

  it("refuses values that could inject extra lines", () => {
    const file = tempEnv("A=1\n");
    expect(() => upsertEnvValues(file, { A: "x\nEVIL=1" })).toThrow(/refusing/);
    expect(() => upsertEnvValues(file, { "bad key": "x" })).toThrow(/refusing/);
    expect(fs.readFileSync(file, "utf-8")).toBe("A=1\n");
  });
});
