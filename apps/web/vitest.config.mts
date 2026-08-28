import react from "@vitejs/plugin-react";
import { configDefaults, defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";

const workspaceRoot = fileURLToPath(new URL("../..", import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": `${workspaceRoot}/apps/web/src`,
      "@itl/design-system": `${workspaceRoot}/packages/design-system/src/index.tsx`,
      "@itl/ui-catalog": `${workspaceRoot}/packages/ui-catalog/src/index.tsx`,
    },
  },
  test: {
    environment: "jsdom",
    exclude: [...configDefaults.exclude, "**/*.browser.spec.ts", "../../.software-factory/mutations/**"],
  },
});
