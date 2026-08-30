import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  buttonCatalogManifest,
  buttonFixtureSpec,
  ControlledRenderer,
  fixtureSpec,
  UI_SPEC_VERSION,
  validateUISpec,
} from "@itl/ui-catalog";
import { afterEach, expect, test, vi } from "vitest";

import { ControlledCanvas } from "./controlled-canvas";

afterEach(cleanup);
afterEach(() => vi.unstubAllGlobals());

function installRefineApi() {
  const fetchMock = vi.fn(async (input: string, _init?: RequestInit) => {
    void _init;
    if (input.endsWith("/v1/refine/parse-critique")) {
      return new Response(JSON.stringify({
        interpretation: {
          targetElementId: "continue-button",
          evidence: {
            likedPaths: ["/appearance/recipe", "/appearance/density"],
            dislikedPaths: ["/appearance/radius"],
            lockedPaths: ["/appearance/recipe", "/appearance/density"],
            strength: "moderate",
          },
          directives: [
            { kind: "keep", path: "/appearance/recipe" },
            { kind: "keep", path: "/appearance/density" },
            { kind: "decrease", path: "/appearance/radius" },
          ],
          ambiguity: [],
          rationale: "Keep recipe and density; decrease radius.",
        },
      }));
    }
    if (input.endsWith("/v1/refine/generate-variants")) {
      return new Response(JSON.stringify({
        variants: [
          { id: "exploit-1", kind: "exploit", direction: "directive-led refinement", spec: buttonFixtureSpec },
          { id: "adjacent-explore-1", kind: "adjacent_explore", direction: "nearby change", spec: buttonFixtureSpec },
        ],
      }));
    }
    return new Response(JSON.stringify({ id: 1, createdAt: "2026-01-01T00:00:00Z" }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

test("ui.valid_spec_renders_deterministically", () => {
  const first = render(<ControlledRenderer spec={fixtureSpec} />);
  const firstButton = screen.getByRole("button", { name: "Continue" });
  const initialHtml = first.container.innerHTML;
  first.rerender(<ControlledRenderer spec={fixtureSpec} />);
  expect(screen.getByRole("button", { name: "Continue" })).toBe(firstButton);
  expect(first.container.innerHTML).toBe(initialHtml);
});

test("button.catalog_manifest_matches_the_typescript_visual_vocabulary", () => {
  const fixture = JSON.parse(
    readFileSync(resolve(process.cwd(), "../../contracts/catalog/button.v1.json"), "utf8"),
  ) as { appearance: typeof buttonCatalogManifest.appearance };
  expect(fixture.appearance).toEqual(buttonCatalogManifest.appearance);
});

test("ui.invalid_specs_fail_closed", () => {
  const badReference = structuredClone(fixtureSpec);
  badReference.elements["welcome-card"].children = ["missing-element"];
  const unknownAppearance: unknown = {
    version: UI_SPEC_VERSION,
    root: "button",
    elements: {
      button: {
        type: "Button",
        props: {
          content: { label: "Continue" },
          semantic: { role: "primary-action", state: "default" },
          appearance: {
            recipe: "primary", size: "regular", radius: "soft", density: "comfortable", fontWeight: "semibold", background: "accent",
          },
        },
        children: [],
      },
    },
  };
  expect(validateUISpec(badReference).valid).toBe(false);
  expect(validateUISpec(unknownAppearance).valid).toBe(false);
  render(<ControlledRenderer spec={unknownAppearance} />);
  expect(screen.getByRole("alert").textContent).toContain("Invalid controlled UI spec");
});

test("ui.button_accessibility_states_pass", () => {
  const loadingSpec = structuredClone(buttonFixtureSpec);
  const button = loadingSpec.elements["continue-button"];
  if (button.type === "Button") button.props.semantic.state = "loading";
  render(<ControlledRenderer spec={loadingSpec} />);
  expect(screen.getByRole("button", { name: "Loading…" })).toHaveProperty("disabled", true);
});

test("ui.generated_props_are_constrained_to_coherent_recipes", () => {
  const invalid: unknown = structuredClone(buttonFixtureSpec);
  const element = (
    invalid as { elements: Record<string, { props: Record<string, unknown> }> }
  ).elements["continue-button"];
  element.props.background = "#ff00ff";
  expect(validateUISpec(invalid).valid).toBe(false);
});

test("button.web_uses_api_and_typed_context", async () => {
  const fetchMock = installRefineApi();
  render(<ControlledCanvas locale="en" />);
  expect(screen.getByRole("region", { name: "Preview" })).toBeDefined();
  expect(screen.getByRole("region", { name: "hero Button surface" })).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "toolbar" }));
  expect(screen.getByRole("region", { name: "toolbar Button surface" })).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "form" }));
  expect(screen.getByRole("region", { name: "form Button surface" })).toBeDefined();
  fireEvent.change(screen.getByLabelText("Critique"), { target: { value: "It is too rounded." } });
  fireEvent.click(screen.getByRole("button", { name: "Review interpretation" }));
  expect(await screen.findByRole("region", { name: "Review refinement interpretation" })).toBeDefined();
  expect(screen.getByRole("separator", { name: "Review feedback" })).toBeDefined();
  expect(screen.getAllByRole("checkbox")).toHaveLength(5);
  fireEvent.click(screen.getByRole("button", { name: "Generate constrained alternatives" }));
  expect(await screen.findByRole("region", { name: "Constrained alternatives" })).toBeDefined();
  expect(screen.getAllByRole("region", { name: "form Button surface" })).toHaveLength(3);
  const preferenceRequest = fetchMock.mock.calls.find(([url]) => String(url).endsWith("/v1/preference-events"));
  expect(preferenceRequest).toBeDefined();
  const requestBody = JSON.parse(String(preferenceRequest?.[1]?.body)) as Record<string, unknown>;
  expect(requestBody).not.toHaveProperty("interpretation");
  expect(requestBody).toHaveProperty("parserInterpretation");
});

test("button.web_does_not_submit_an_empty_critique", () => {
  installRefineApi();
  render(<ControlledCanvas locale="en" />);

  expect(screen.getByRole("button", { name: "Review interpretation" })).toHaveProperty("disabled", true);
});
