import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { fixtureSpec, ControlledRenderer, UI_SPEC_VERSION, validateUISpec } from "@itl/ui-catalog";
import { afterEach, expect, test } from "vitest";

import { ControlledCanvas } from "./controlled-canvas";

afterEach(cleanup);

test("ui.valid_spec_renders_deterministically", () => {
  const first = render(<ControlledRenderer spec={fixtureSpec} />);
  const firstButton = screen.getByRole("button", { name: "Continue" });
  const initialHtml = first.container.innerHTML;

  first.rerender(<ControlledRenderer spec={fixtureSpec} />);

  expect(screen.getByRole("button", { name: "Continue" })).toBe(firstButton);
  expect(first.container.innerHTML).toBe(initialHtml);
});

test("ui.invalid_specs_fail_closed", () => {
  const badReference = structuredClone(fixtureSpec);
  badReference.elements["welcome-card"].children = ["missing-element"];
  const cycle = structuredClone(fixtureSpec);
  cycle.elements["welcome-card"].children = ["welcome-card"];
  const unknownComponent = {
    version: UI_SPEC_VERSION,
    root: "unknown",
    elements: { unknown: { type: "Unknown", props: {}, children: [] } },
  };
  const unknownProp: unknown = {
    version: UI_SPEC_VERSION,
    root: "button",
    elements: {
      button: {
        type: "Button",
        props: { label: "Continue", variant: "solid", size: "regular", radius: "soft", density: "comfortable", background: "accent", foreground: "light", border: "none", fontWeight: "semibold", state: "default", className: "free-form-css" },
        children: [],
      },
    },
  };

  expect(validateUISpec(badReference).valid).toBe(false);
  expect(validateUISpec(cycle).valid).toBe(false);
  expect(validateUISpec(unknownComponent).valid).toBe(false);
  expect(validateUISpec(unknownProp).valid).toBe(false);

  render(<ControlledRenderer spec={unknownComponent} />);
  expect(screen.getByRole("alert").textContent).toContain("Invalid controlled UI spec");
});

test("ui.button_accessibility_states_pass", () => {
  const loadingSpec = structuredClone(fixtureSpec);
  const button = loadingSpec.elements["continue-button"];
  if (button.type === "Button") button.props.state = "loading";

  render(<ControlledRenderer spec={loadingSpec} />);

  const loadingButton = screen.getByRole("button", { name: "Loading…" });
  expect(loadingButton).toHaveProperty("disabled", true);
  expect(loadingButton.getAttribute("aria-busy")).toBe("true");

  const enabled = render(<ControlledRenderer spec={fixtureSpec} />).getByRole("button", { name: "Continue" });
  enabled.focus();
  expect(document.activeElement).toBe(enabled);
});

test("ui.generated_props_are_constrained", () => {
  const freeFormColor: unknown = {
    version: UI_SPEC_VERSION,
    root: "button",
    elements: {
      button: {
        type: "Button",
        props: { label: "Continue", variant: "solid", size: "regular", radius: "soft", density: "comfortable", background: "#ff00ff", foreground: "light", border: "none", fontWeight: "semibold", state: "default" },
        children: [],
      },
    },
  };

  expect(validateUISpec(freeFormColor).valid).toBe(false);
});

test("ui.storybook_matches_catalog", () => {
  render(<ControlledCanvas />);

  expect(screen.getByRole("button", { name: "Continue" })).toBeDefined();
  expect(screen.getByLabelText("Name")).toBeDefined();
  expect(screen.getByText("Ready")).toBeDefined();
  expect(screen.getByRole("region", { name: "Controlled components" })).toBeDefined();

  fireEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(screen.getByTestId("selected-element").textContent).toContain("continue-button");
});
