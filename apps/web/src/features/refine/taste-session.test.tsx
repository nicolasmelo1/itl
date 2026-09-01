import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { ControlledCanvas } from "../canvas/controlled-canvas";
import { currentSessionId } from "./session";

/**
 * The acquisition client is the other half of corpus integrity. A store that
 * resolves to one path is worth nothing if every judgment written into it
 * still claims to come from the same session.
 */
const SESSION_ID_CONTRACT = /^[a-zA-Z0-9][a-zA-Z0-9_-]{7,79}$/;
const RESERVED = ["local", "default", "session", "anonymous", "unknown"];

afterEach(cleanup);
afterEach(() => vi.unstubAllGlobals());
afterEach(() => window.sessionStorage.clear());

function installMemoryApi() {
  const fetchMock = vi.fn(async (input: string, init?: RequestInit) => {
    void input;
    void init;
    return new Response(JSON.stringify({ id: 1, createdAt: "2026-08-31T00:00:00Z" }));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function recordedJudgments(fetchMock: ReturnType<typeof installMemoryApi>) {
  return fetchMock.mock.calls
    .map(([, init]) => JSON.parse(String(init?.body)) as Record<string, unknown>)
    .filter((body) => typeof body.action === "string");
}

test("taste.a_session_id_is_real_and_stable_within_one_session", () => {
  const first = currentSessionId();

  expect(first).toMatch(SESSION_ID_CONTRACT);
  expect(RESERVED).not.toContain(first);
  expect(currentSessionId()).toBe(first);
});

test("taste.every_recorded_judgment_carries_that_session_id", () => {
  const fetchMock = installMemoryApi();
  render(<ControlledCanvas locale="en" />);

  fireEvent.change(screen.getByLabelText("Edit radius"), { target: { value: "square" } });

  const judgments = recordedJudgments(fetchMock);
  expect(judgments.length).toBeGreaterThan(0);
  for (const judgment of judgments) {
    expect(String(judgment.sessionId)).toMatch(SESSION_ID_CONTRACT);
    expect(RESERVED).not.toContain(judgment.sessionId);
  }
});

test("taste.a_judgment_names_the_product_tone_it_was_made_under", () => {
  const fetchMock = installMemoryApi();
  render(<ControlledCanvas locale="en" />);

  fireEvent.change(screen.getByLabelText("Edit radius"), { target: { value: "square" } });
  expect(recordedJudgments(fetchMock).at(-1)?.projectContext).toMatchObject({
    productKind: "saas",
    visualTone: ["serious", "minimal"],
  });

  // The same usage under another product tone is a different reading, not a
  // contradiction, so the tone travels with the judgment.
  fireEvent.click(screen.getByRole("button", { name: "playful" }));
  fireEvent.change(screen.getByLabelText("Edit radius"), { target: { value: "pill" } });
  expect(recordedJudgments(fetchMock).at(-1)?.projectContext).toMatchObject({
    productKind: "marketing",
    visualTone: ["playful", "expressive"],
  });
});
