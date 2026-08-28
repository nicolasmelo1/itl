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

test("a critique is confirmed before constrained alternatives are reviewed", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("Optional critique").fill("I like the color and spacing, but it is too rounded.");
  await page.getByRole("button", { name: "Review interpretation" }).click();
  await expect(page.getByRole("region", { name: "Review refinement intent" })).toBeVisible();
  await page.getByRole("button", { name: "Generate constrained alternatives" }).click();
  await expect(page.getByText("exploit", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Reject all" }).click();
  await expect(page.getByTestId("refine-status")).toContainText("No option was selected as a winner");
});
