import { expect, test } from "@playwright/test";

test("the canvas exposes registered atoms and stable selection identifiers", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("region", { name: "Controlled components" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue" })).toBeEnabled();
  await expect(page.getByLabel("Name")).toBeVisible();
  await expect(page.getByText("Ready")).toBeVisible();
  await expect(page.locator("[data-jr-key='continue-button']")).toHaveCount(1);

  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByTestId("selected-element")).toContainText("continue-button");
});
