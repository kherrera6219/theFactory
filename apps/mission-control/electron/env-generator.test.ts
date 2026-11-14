import fs from "fs";
import os from "os";
import path from "path";
import { afterEach, describe, expect, it } from "vitest";
import { generateEnvFile, releaseModelDefaults, upsertEnvValues } from "./env-generator";
import { parseEnvText } from "./factory-stack";

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

describe("generateEnvFile", () => {
  it("makes a vault key the vault can actually use", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "hgr-gen-"));
    dirs.push(dir);
    const out = path.join(dir, "backend.env");
    generateEnvFile({
      templatePath: path.join(__dirname, "..", "..", "..", ".env.example"),
      outputEnvPath: out,
      llmKeys: { gemini: "test-key" },
    });
    const env = parseEnvText(fs.readFileSync(out, "utf-8"));
    // vault.ts isValidEncryptionKey: exactly 64 hex chars (AES-256).
    expect(env.MISSION_CONTROL_ADMIN_KEY).toMatch(/^[0-9a-f]{64}$/);
    // ORCHESTRATOR_API_KEYS is "<key>=<scopes>": the gateway must accept the
    // very key Mission Control calls it with.
    expect(env.ORCHESTRATOR_API_KEYS.split("=")[0]).toBe(env.INTERNAL_SERVICE_API_KEY);
    expect(Object.values(env).some((v) => v.includes("CHANGE_ME"))).toBe(false);
  });
});

describe("releaseModelDefaults", () => {
  it("reads only the model keys from the template and refreshes a stale env", () => {
    const template = tempEnv(
      "GEMINI_MODEL=gemini-4-argon\nOPENAI_MODEL=gpt-6.1-terrea\nANTHROPIC_MODEL=claude-ops-5.5\nGEMINI_API_KEY=secret\n# GEMINI_MODEL=old\n",
    );
    const defaults = releaseModelDefaults(template);
    expect(defaults).toEqual({
      GEMINI_MODEL: "gemini-4-argon",
      OPENAI_MODEL: "gpt-6.1-terrea",
      ANTHROPIC_MODEL: "claude-ops-5.5",
    });
    const env = tempEnv("GEMINI_MODEL=gemini-3.8-flash\nGEMINI_API_KEY=keep\n");
    upsertEnvValues(env, defaults);
    const text = fs.readFileSync(env, "utf-8");
    expect(text).toContain("GEMINI_MODEL=gemini-4-argon");
    expect(text).toContain("GEMINI_API_KEY=keep");
  });
});
