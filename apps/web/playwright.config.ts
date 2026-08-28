import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./src/features/canvas",
  testMatch: "**/*.browser.spec.ts",
  use: {
    baseURL: "http://127.0.0.1:3200",
    browserName: "chromium",
    channel: "chrome",
  },
  webServer: {
    command: "pnpm dev --port 3200",
    port: 3200,
    reuseExistingServer: !process.env.CI,
  },
});
