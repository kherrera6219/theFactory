import { defineConfig, devices } from "@playwright/test";

const testMissionControlAdminKey =
  process.env.MISSION_CONTROL_ADMIN_KEY ?? "mission-control-admin-key-for-tests";
const testMissionControlSessionSecret =
  process.env.MISSION_CONTROL_SESSION_SECRET ??
  "mission-control-session-secret-for-tests";

const webServerEnv = Object.entries(process.env).reduce<Record<string, string>>(
  (accumulator, [key, value]) => {
    if (key !== "NO_COLOR" && typeof value === "string") {
      accumulator[key] = value;
    }
    return accumulator;
  },
  {},
);

webServerEnv.MISSION_CONTROL_ADMIN_KEY ??= testMissionControlAdminKey;
webServerEnv.MISSION_CONTROL_SESSION_SECRET ??= testMissionControlSessionSecret;
webServerEnv.MISSION_CONTROL_SESSION_SECURE ??= "false";
webServerEnv.MISSION_API_BASE_URL = "http://localhost:8100";
webServerEnv.NEXT_PUBLIC_API_BASE_URL = "http://localhost:8100";

const reuseExistingServer = process.env.PLAYWRIGHT_REUSE_SERVER === "true";

export default defineConfig({
  testDir: "./e2e",
  // Electron E2E runs against a launched desktop app, not the Next web server.
  // It has its own config (playwright.electron.config.ts) and must not be swept
  // into the default chromium/web-server run.
  testIgnore: ["**/electron.spec.ts"],
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  fullyParallel: true,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
    headless: true,
  },
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3000",
    env: webServerEnv,
    url: "http://127.0.0.1:3000",
    reuseExistingServer,
    timeout: 120_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
