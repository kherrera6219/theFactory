import { expect, test } from "@playwright/test";

import { attachOperatorSession } from "./test-helpers";

test.beforeEach(async ({ page }) => {
  await attachOperatorSession(page);
});

test("chat is the SOW front door for new work and ZIP import", async ({ page }) => {
  await page.goto("/chat");
  await expect(page.getByRole("heading", { name: "Mission Intake Conversation" })).toBeVisible();
  await expect(page.getByText("Attach project (ZIP)")).toBeVisible();
  await expect(
    page.getByText(/Statement of Work|Feature Contract|Contract appears after the PM/),
  ).toBeVisible();
});

test("repo review hands off to PM instead of launching a raw mission", async ({ page }) => {
  await page.goto("/repo");
  await expect(page.getByRole("heading", { name: /Repository Intake/ })).toBeVisible();
  await expect(page.getByText("Continue with PM")).toBeVisible();
});
