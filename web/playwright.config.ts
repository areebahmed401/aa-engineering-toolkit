import { defineConfig, devices } from "@playwright/test";

// Runs the production build (npm run build) through the real Pyodide worker in Chromium.
export default defineConfig({
  testDir: "./e2e",
  timeout: 240_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: { baseURL: "http://localhost:4173/", ...devices["Desktop Chrome"], trace: "retain-on-failure" },
  webServer: { command: "npm run preview", url: "http://localhost:4173/", reuseExistingServer: !process.env.CI, timeout: 60_000 },
});
