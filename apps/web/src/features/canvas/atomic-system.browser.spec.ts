import { expect, test } from "@playwright/test";

test("atomic.accessibility_and_responsive_states_hold_at_every_layer", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/en/atomic");

  await expect(page.getByRole("main", { name: "Project settings" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Account", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Account email", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Save changes" }).focus();
  await expect(page.getByRole("button", { name: "Save changes" })).toBeFocused();

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.getByRole("main", { name: "Project settings" })).toBeVisible();
});
