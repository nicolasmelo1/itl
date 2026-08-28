import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import Home from "./page";

test("renders the empty application shell", () => {
  render(<Home />);

  expect(screen.getByRole("main")).toBeDefined();
});
