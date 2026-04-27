/**
 * ASTRA demo automation — Playwright walks through the 4-min judge demo.
 *
 *   npx playwright test e2e/demo.spec.ts --headed --workers=1
 *
 * Requirements (operator runs once):
 *   npm install -D @playwright/test
 *   npx playwright install chromium
 *
 * Backend must be running on http://127.0.0.1:8000 and frontend on
 * http://localhost:5173 (or override via DEMO_BASE_URL).
 *
 * Records WebM video by default (Playwright config). Use as a backup
 * recording if the live demo hits a snag on stage.
 */
import { test, expect } from "@playwright/test";

const BASE = process.env.DEMO_BASE_URL ?? "http://localhost:5173";

test.describe.configure({ mode: "serial" });

test("ASTRA 4-min demo walkthrough", async ({ page }) => {
  test.setTimeout(5 * 60 * 1000); // 5 min cap

  // 0. Splash + landing
  await page.goto(BASE);
  await page.waitForTimeout(2200); // let splash play
  await page.locator("body").click(); // skip if still showing
  await expect(page).toHaveURL(/\/command/);
  await expect(page.getByText("COMMAND CENTER")).toBeVisible();
  await page.waitForTimeout(2000);

  // 1. Mission page — show cascade
  await page.goto(`${BASE}/mission`);
  await expect(page.getByText("Live Mission Feed")).toBeVisible();
  await page.waitForTimeout(2500);

  // 2. Map
  await page.goto(`${BASE}/map`);
  await expect(page.getByText("Tactical Map")).toBeVisible();
  await page.waitForTimeout(3000);

  // 3. Alerts — trigger waveform visible
  await page.goto(`${BASE}/alerts`);
  await expect(page.getByText(/Threat Queue/i)).toBeVisible();
  await page.waitForTimeout(2500);

  // 4. Federated — topology
  await page.goto(`${BASE}/federated`);
  await expect(page.getByText(/Federated/i)).toBeVisible();
  await page.waitForTimeout(3500);

  // 5. Adversarial — A/B retention
  await page.goto(`${BASE}/adversarial`);
  await expect(page.getByText(/Adversarial/i)).toBeVisible();
  await page.waitForTimeout(3000);

  // 6. Audit — chain badge
  await page.goto(`${BASE}/audit`);
  await expect(page.getByText("Audit Log")).toBeVisible();
  // Trigger verify chain
  await page.getByRole("button", { name: /verify chain/i }).click().catch(() => { /* optional */ });
  await page.waitForTimeout(2500);

  // 7. Benchmark — final number wall
  await page.goto(`${BASE}/benchmark`);
  await expect(page.getByText("Benchmark")).toBeVisible();
  await page.waitForTimeout(3500);

  // 8. Back to Command Center for the close
  await page.goto(`${BASE}/command`);
  await page.waitForTimeout(3000);
});
