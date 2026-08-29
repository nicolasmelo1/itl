import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import Home from "./page";

test("renders the English application shell", async () => {
  render(await Home({
    params: Promise.resolve({ locale: "en" }),
  }));

  expect(screen.getByRole("main")).toBeDefined();
});
