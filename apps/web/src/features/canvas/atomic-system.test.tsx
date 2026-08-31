import { ControlledRenderer, projectSettingsFixtureSpec, validateUISpec } from "@itl/ui-catalog";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

afterEach(cleanup);

test("atomic.templates_and_pages_render_only_registered_structures", () => {
  render(<ControlledRenderer spec={projectSettingsFixtureSpec} />);
  expect(screen.getByRole("main", { name: "Project settings" })).toBeDefined();
  expect(screen.getByRole("heading", { name: "Project settings", level: 1 })).toBeDefined();
  expect(screen.getByRole("region", { name: "Account" })).toBeDefined();
  expect(screen.getByRole("region", { name: "Account email" })).toBeDefined();
  expect(screen.getByRole("button", { name: "Save changes" })).toHaveProperty("disabled", false);

  const invalid = structuredClone(projectSettingsFixtureSpec);
  invalid.elements["settings-template"].children = ["account-email"];
  expect(validateUISpec(invalid)).toMatchObject({ valid: false, issues: [{ code: "parent-child" }] });
});
