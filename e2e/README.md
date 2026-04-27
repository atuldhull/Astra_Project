# ASTRA — Demo automation (Playwright)

Records a backup video of the 4-minute judge demo. Use it if the live
walkthrough hits a snag on stage.

## One-time setup
```bash
cd /c/Users/atuld/OneDrive/Desktop/astra
npm install -D @playwright/test
npx playwright install chromium
```

## Run
```bash
# headed (you watch it)
npx playwright test --config=e2e/playwright.config.ts --headed

# headless + record video only
npx playwright test --config=e2e/playwright.config.ts
```

Videos land in `test-results/`. Screenshot on failure, trace zip on
failure. Override the base URL with `DEMO_BASE_URL=http://...` env var.
