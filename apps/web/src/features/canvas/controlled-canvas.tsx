"use client";

import { markDevtoolsActive } from "@json-render/core";
import { ControlledRenderer, fixtureSpec } from "@itl/ui-catalog";
import { type MouseEvent, useEffect, useState } from "react";

import styles from "./controlled-canvas.module.css";

export function ControlledCanvas() {
  const [selectedElementId, setSelectedElementId] = useState(fixtureSpec.root);

  useEffect(() => markDevtoolsActive(), []);

  return (
    <main className={styles.canvas} onClick={selectElement(setSelectedElementId)}>
      <div className={styles.workbench}>
        <ControlledRenderer spec={fixtureSpec} />
        <p aria-live="polite" className={styles.selection} data-testid="selected-element">
          Selected element: {selectedElementId}
        </p>
      </div>
    </main>
  );
}

function selectElement(setSelectedElementId: (elementId: string) => void) {
  return (event: MouseEvent<HTMLElement>) => {
    const target = event.target;
    if (!(target instanceof Element)) return;

    const element = target.closest<HTMLElement>("[data-jr-key]");
    const elementId = element?.dataset.jrKey;
    if (elementId) setSelectedElementId(elementId);
  };
}
