import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const originalFetch = global.fetch;
// These vault.ts module-level constants are captured once at import time
// from process.env, so they must be cleared *before* the dynamic import in
// each test -- otherwise whatever the host shell/.env happens to have set
// for these override vars would leak in and make the expected URLs wrong.
const OVERRIDE_VARS = ["OPENAI_BASE_URL", "ANTHROPIC_BASE_URL", "ANTHROPIC_VERSION", "GEMINI_BASE_URL"] as const;
const originalOverrides = Object.fromEntries(OVERRIDE_VARS.map((name) => [name, process.env[name]]));

async function loadPreflight() {
  vi.resetModules();
  const module = await import("./vault");
  return module.preflightProviderCall;
}

beforeEach(() => {
  for (const name of OVERRIDE_VARS) {
    delete process.env[name];
  }
});

afterEach(() => {
  global.fetch = originalFetch;
  vi.restoreAllMocks();
  for (const name of OVERRIDE_VARS) {
    const value = originalOverrides[name];
    if (value === undefined) {
      delete process.env[name];
    } else {
      process.env[name] = value;
    }
  }
});

describe("preflightProviderCall", () => {
  it("reports OpenAI valid when the models list call succeeds", async () => {
    const preflightProviderCall = await loadPreflight();
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await preflightProviderCall("openai", "sk-test-key-123456");

    expect(result).toEqual({
      valid: true,
      reason: "OpenAI accepted the key (models list call succeeded).",
      live_checked: true,
    });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.openai.com/v1/models");
    expect(init.method).toBe("GET");
    expect(init.headers.Authorization).toBe("Bearer sk-test-key-123456");
  });

  it("reports OpenAI invalid on a non-2xx response", async () => {
    const preflightProviderCall = await loadPreflight();
    global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 401 }) as unknown as typeof fetch;

    const result = await preflightProviderCall("openai", "sk-bad-key");

    expect(result.valid).toBe(false);
    expect(result.reason).toContain("HTTP 401");
    expect(result.live_checked).toBe(true);
  });

  it("sends the correct Anthropic request shape and reports success", async () => {
    const preflightProviderCall = await loadPreflight();
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await preflightProviderCall("anthropic", "sk-ant-test-key", "claude-opus-4-8");

    expect(result.valid).toBe(true);
    expect(result.live_checked).toBe(true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("https://api.anthropic.com/v1/messages");
    expect(init.headers["x-api-key"]).toBe("sk-ant-test-key");
    expect(init.headers["anthropic-version"]).toBe("2023-06-01");
    const body = JSON.parse(init.body as string);
    expect(body.model).toBe("claude-opus-4-8");
    expect(body.max_tokens).toBe(1);
  });

  it("sends the correct Gemini request shape and reports success", async () => {
    const preflightProviderCall = await loadPreflight();
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await preflightProviderCall("gemini", "AIzaTestKey1234567890", "gemini-3.7-flash");

    expect(result.valid).toBe(true);
    expect(result.live_checked).toBe(true);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.7-flash:generateContent?key=AIzaTestKey1234567890",
    );
    const body = JSON.parse(init.body as string);
    expect(body.generationConfig.maxOutputTokens).toBe(1);
  });

  it("preflights a superseded Gemini revision against the current model", async () => {
    const preflightProviderCall = await loadPreflight();
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    global.fetch = fetchMock as unknown as typeof fetch;

    await preflightProviderCall("gemini", "AIzaTestKey1234567890", "gemini-3.5-flash");

    // Testing the key against a model the app no longer routes to would report
    // health for something no mission will ever use.
    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain("gemini-3.7-flash:generateContent");
    expect(url).not.toContain("gemini-3.5-flash");
  });

  it("returns a network-error result without throwing when fetch rejects", async () => {
    const preflightProviderCall = await loadPreflight();
    global.fetch = vi.fn().mockRejectedValue(new Error("getaddrinfo ENOTFOUND")) as unknown as typeof fetch;

    const result = await preflightProviderCall("openai", "sk-test-key-123456");

    expect(result.valid).toBe(false);
    expect(result.live_checked).toBe(false);
    expect(result.reason).toContain("Unable to reach openai");
  });

  it("falls back to format-only validity for providers with no live call defined", async () => {
    const preflightProviderCall = await loadPreflight();
    const fetchMock = vi.fn();
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await preflightProviderCall("github", "ghp_abcdefghijklmnop");

    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.valid).toBe(true);
    expect(result.live_checked).toBe(false);
  });
});
