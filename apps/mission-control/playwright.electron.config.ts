import { defineConfig } from "@playwright/test";

// Electron E2E launches the built desktop app directly (no Next web server).
// Run `npm run electron:build` first so dist/electron/electron/main.js exists.
export default defineConfig({
  testDir: "./e2e",
  testMatch: ["**/electron.spec.ts"],
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  fullyParallel: false,
  workers: 1,
  reporter: "list",
});
