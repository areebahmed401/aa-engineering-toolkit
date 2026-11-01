import { defineConfig, devices } from "@playwright/test";

// Runs the production build (npm run build) through the real Pyodide worker in Chromium.
// E2E_PORT picks another preview port (e.g. when several checkouts run tests at once).
const PORT = process.env.E2E_PORT ?? "4173";

export default defineConfig({
  testDir: "./e2e",
  timeout: 240_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: `http://localhost:${PORT}/`, ...devices["Desktop Chrome"], trace: "retain-on-failure" },
  webServer: { command: `npx vite preview --port ${PORT} --strictPort`, url: `http://localhost:${PORT}/`, reuseExistingServer: !process.env.CI, timeout: 60_000 },
});
