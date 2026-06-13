import path from "node:path";

import { test, expect, type ElectronApplication, type Page } from "@playwright/test";
import { _electron as electron } from "playwright";

// Built Electron entry point. `electron:build` compiles electron/main.ts to
// dist/electron/electron/main.js (see package.json "main"). Run that build
// before this suite (the CI job below does `npm run electron:build`).
const ELECTRON_MAIN = path.join(__dirname, "..", "dist", "electron", "electron", "main.js");

let app: ElectronApplication;
let page: Page;

test.beforeAll(async () => {
  app = await electron.launch({
    args: [ELECTRON_MAIN],
    env: {
      ...process.env,
      ELECTRON_E2E: "1",
    },
  });
  page = await app.firstWindow();
});

test.afterAll(async () => {
  await app?.close().catch(async () => {
    await app?.process().kill();
  });
});

test("app launches and shows the operator window", async () => {
  await expect(page).toHaveTitle(/Mission Control|theFactory/);
});

test("navigation guard blocks external URLs", async () => {
  // setWindowOpenHandler denies any non-localhost / non-file:// URL and routes it
  // to the system browser instead, so no second Electron window should appear.
  const [newWindow] = await Promise.all([
    app.waitForEvent("window", { timeout: 2_000 }).catch(() => null),
    page.evaluate(() => {
      window.open("https://example.com");
    }),
  ]);
  expect(newWindow).toBeNull();
});
