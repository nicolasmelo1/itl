import { expect, test } from "@playwright/test";
import { buttonFixtureSpec } from "@itl/ui-catalog";

test("the contextual canvas exposes one editable Button in each static surface", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("region", { name: "hero Button surface" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Continue" })).toBeEnabled();
  await page.getByRole("button", { name: "toolbar" }).click();
  await expect(page.getByRole("region", { name: "toolbar Button surface" })).toBeVisible();
  await page.getByRole("button", { name: "form" }).click();
  await expect(page.getByRole("region", { name: "form Button surface" })).toBeVisible();
});

test("a critique stays transient until its contextual interpretation is confirmed", async ({ page }) => {
  const recordedActions: string[] = [];
  await page.route("**/v1/**", async (route) => {
    if (route.request().url().endsWith("/v1/refine/parse-critique")) {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          interpretation: {
            targetElementId: "continue-button",
            evidence: { likedPaths: [], dislikedPaths: ["/appearance/radius"], lockedPaths: [], strength: "moderate" },
            directives: [{ kind: "decrease", path: "/appearance/radius" }],
            ambiguity: [],
            rationale: "Decrease radius.",
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
            { id: "exploit-1", kind: "exploit", direction: "directive-led refinement", spec: buttonFixtureSpec },
          ],
        }),
      });
      return;
    }
    const body = route.request().postDataJSON() as { action?: string };
    if (body.action) recordedActions.push(body.action);
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ id: 1, createdAt: "2026-01-01T00:00:00Z" }),
    });
  });
  await page.goto("/");
  await page.getByLabel("Optional critique").fill("It is too rounded.");
  await page.getByRole("button", { name: "Review interpretation" }).click();
  await expect(page.getByRole("region", { name: "Review refinement interpretation" })).toBeVisible();
  expect(recordedActions).toEqual([]);
  await page.getByRole("button", { name: "Generate constrained alternatives" }).click();
  await expect(page.getByText("exploit: directive-led refinement")).toBeVisible();
  expect(recordedActions).toContain("confirmed_critique");
});
