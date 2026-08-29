import { expect, test } from "@playwright/test";
import { fixtureSpec } from "@itl/ui-catalog";

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
  const recordedActions: string[] = [];
  await page.route("**/v1/**", async (route) => {
    if (route.request().url().endsWith("/v1/refine/parse-critique")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          intent: {
            targetElementId: "continue-button",
            likedPaths: ["/props/background", "/props/density"],
            dislikedPaths: ["/props/radius"],
            lockedPaths: ["/props/background", "/props/density"],
            explorationPaths: ["/props/radius"],
            ambiguity: [],
            rationale: "Keep color and density; explore radius.",
          },
        }),
      });
      return;
    }
    if (route.request().url().endsWith("/v1/refine/generate-variants")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          variants: [
            { id: "exploit-1", kind: "exploit", spec: fixtureSpec },
            { id: "adjacent-explore-1", kind: "adjacent_explore", spec: fixtureSpec },
          ],
        }),
      });
      return;
    }
    const body = route.request().postDataJSON() as { action?: string };
    if (body.action) recordedActions.push(body.action);
    await route.fulfill({ contentType: "application/json", body: JSON.stringify({ id: 1, createdAt: "2026-01-01T00:00:00Z" }) });
  });
  await page.goto("/");

  await page.getByLabel("Optional critique").fill("I like the color and spacing, but it is too rounded.");
  await page.getByRole("button", { name: "Review interpretation" }).click();
  await expect(page.getByRole("region", { name: "Review refinement intent" })).toBeVisible();
  expect(recordedActions).toEqual([]);
  await page.getByRole("button", { name: "Generate constrained alternatives" }).click();
  await expect(page.getByText("exploit", { exact: true })).toBeVisible();
  expect(recordedActions).toContain("confirmed_critique");
  await page.getByRole("button", { name: "Reject all" }).click();
  await expect(page.getByTestId("refine-status")).toContainText("No option was selected as a winner");
});
