import { defineConfig, devices } from "@playwright/test";

/**
 * Operator-run config. Records WebM video of every test, takes a screenshot
 * on failure, and uses the chromium browser at 1920x1080 (judge-laptop scale).
 *
 *   npx playwright test --config=e2e/playwright.config.ts --headed
 */
export default defineConfig({
  testDir: ".",
  timeout: 5 * 60 * 1000,
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: process.env.DEMO_BASE_URL ?? "http://localhost:5173",
    headless: false,
    viewport: { width: 1920, height: 1080 },
    video: "on",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
