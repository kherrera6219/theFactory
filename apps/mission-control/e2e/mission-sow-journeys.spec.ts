import { expect, test } from "@playwright/test";

import { attachOperatorSession } from "./test-helpers";

test.beforeEach(async ({ page }) => {
  await attachOperatorSession(page);
});

test("chat is the SOW front door for new work and ZIP import", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Mission Intake Conversation" })).toBeVisible();
  await expect(page.getByText("Attach project (ZIP)")).toBeVisible();
  // Anchored to the panel heading, not a text regex: the earlier broad
  // alternation matched four nodes on this page (the intro copy, the PM
  // greeting, this heading, and the empty-state) and failed strict mode.
  await expect(page.getByRole("heading", { name: "Feature Contract" })).toBeVisible();
});

test("repo review hands off to PM instead of launching a raw mission", async ({ page }) => {
  await page.goto("/repo");
  await expect(page.getByRole("heading", { name: /Repository Intake/ })).toBeVisible();
  await expect(page.getByText("Continue with PM")).toBeVisible();
});
