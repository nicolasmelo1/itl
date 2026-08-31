import { expect, test } from "@playwright/test";

test("atomic.settings_slice_has_basic_responsive_and_keyboard_proof", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/en/atomic");

  await expect(page.getByRole("main", { name: "Project settings" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Account", exact: true })).toBeVisible();
  await expect(page.getByRole("region", { name: "Account email", exact: true })).toBeVisible();
  const saveButton = page.getByRole("button", { name: "Save changes" });
  await saveButton.focus();
  await expect(saveButton).toBeFocused();
  await expect(saveButton).toHaveCSS("transition-duration", "0s");

  await page.setViewportSize({ width: 1440, height: 900 });
  await expect(page.getByRole("main", { name: "Project settings" })).toBeVisible();
});
