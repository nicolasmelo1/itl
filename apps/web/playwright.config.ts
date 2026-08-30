import { defineConfig } from "@playwright/test";

const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:3200";

export default defineConfig({
  testDir: "./src/features/canvas",
  testMatch: "**/*.browser.spec.ts",
  use: {
    baseURL,
    browserName: "chromium",
    channel: "chrome",
  },
  webServer: process.env.PLAYWRIGHT_BASE_URL ? undefined : {
    command: "pnpm dev --port 3200",
    port: 3200,
    reuseExistingServer: !process.env.CI,
  },
});
