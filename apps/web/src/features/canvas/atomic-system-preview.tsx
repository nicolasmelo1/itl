"use client";

import { ControlledRenderer, projectSettingsFixtureSpec } from "@itl/ui-catalog";

export function AtomicSystemPreview() {
  return <ControlledRenderer spec={projectSettingsFixtureSpec} />;
}
