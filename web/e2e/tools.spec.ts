import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

type Tool = { id: string; name: string; has_charts: boolean };
const schema = JSON.parse(
  readFileSync(fileURLToPath(new URL("../public/py/schema.json", import.meta.url)), "utf-8"),
) as { tools: Tool[] };

// Tools whose default inputs use CoolProp's full HEOS library (slow first load in the browser)
const HEOS_TOOLS = new Set(["thermo.refrigeration_cycle"]);
// Tools that register charts but return none for their defaults
const NO_CHARTS = new Set(["thermo.cooling_tower"]);

test.describe.configure({ mode: "serial" });

let page: Page;

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  await page.goto("./");
  await expect(page.getByRole("heading", { name: /Engineering Toolkit/ })).toBeVisible();
  await expect(page.locator('[data-testid="engine-status"]').first()).toHaveAttribute("data-stage", "ready", { timeout: 180_000 });
});

test.afterAll(async () => page.close());

test("home lists every registered tool", async () => {
  await page.goto("./#/");
  for (const tool of schema.tools) {
    await expect(page.getByRole("main").getByRole("link", { name: tool.name, exact: true })).toBeVisible();
  }
});

for (const tool of schema.tools) {
  test(`${tool.id} calculates in the browser`, async () => {
    test.setTimeout(HEOS_TOOLS.has(tool.id) ? 240_000 : 60_000);
    await page.goto(`./#/tool/${tool.id}`);
    await expect(page.getByRole("heading", { level: 1, name: tool.name })).toBeVisible();
    await page.getByTestId("calculate").click();
    await expect(page.getByTestId("results")).toBeVisible({ timeout: HEOS_TOOLS.has(tool.id) ? 200_000 : 45_000 });
    await expect(page.getByTestId("run-error")).toHaveCount(0);
    if (tool.has_charts && !NO_CHARTS.has(tool.id)) {
      await expect(page.locator('[data-testid^="chart-"] .main-svg').first()).toBeVisible();
    }
  });
}

test("shared link reproduces inputs and validation errors show on the field", async () => {
  // q_max = 40 W/m encoded in the URL
  const encoded = Buffer.from(JSON.stringify({ q_max: 40 })).toString("base64url");
  await page.goto(`./#/tool/thermo.insulation_thickness?i=${encoded}`);
  await expect(page.getByTestId("result-heat_loss")).toContainText("40");

  await page.goto("./#/tool/thermo.cooling_tower");
  const rh = page.getByLabel(/Relative humidity/);
  await rh.fill("2");
  await page.getByTestId("calculate").click();
  await expect(page.getByTestId("run-error")).toBeVisible();
});

test("battery page: cooling picker, several C-rates and PyBaMM overlay", async () => {
  test.setTimeout(90_000);
  await page.goto("./#/tool/electrical.battery_simulator");
  await expect(page.getByRole("heading", { level: 1, name: "Battery cell simulator" })).toBeVisible();
  await expect(page.getByLabel(/Liquid coolant/)).toHaveCount(0);
  await page.getByTestId("battery-cooling").getByRole("radio", { name: "Cold plate" }).click();
  await expect(page.getByLabel(/Liquid coolant/)).toBeVisible();
  await page.getByRole("button", { name: "0.2, 0.5, 1" }).click();
  await page.getByTestId("calculate").click();
  await expect(page.getByTestId("results")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("run-error")).toHaveCount(0);
  for (const id of ["voltage", "temperature", "soc", "heat", "capacity_fade"]) {
    await expect(page.locator(`[data-testid="chart-${id}"] .main-svg`).first()).toBeVisible();
  }
  await expect(page.getByTestId("chart-voltage").getByText(/PyBaMM DFN 1C/).first()).toBeVisible();
  await expect(page.getByText(/Mean heat \[W\/cell\]/)).toBeVisible();
});
