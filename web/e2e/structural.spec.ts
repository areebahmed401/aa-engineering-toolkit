import { expect, test, type Page } from "@playwright/test";

// The dedicated structural page: section designer and beam builder with the live FBD.

test.describe.configure({ mode: "serial" });

let page: Page;

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  await page.goto("./#/structural");
  await expect(page.locator('[data-testid="engine-status"]').first()).toHaveAttribute("data-stage", "ready", { timeout: 180_000 });
});

test.afterAll(async () => page.close());

test("old tool links open the structural page", async () => {
  await page.goto("./#/tool/structural.beam_analysis");
  await expect(page).toHaveURL(/#\/structural\?tab=beam/);
  await expect(page.getByRole("heading", { level: 1, name: "Beam analysis" })).toBeVisible();
});

test("section designer shows only the chosen shape's dimensions and draws it", async () => {
  await page.goto("./#/structural?tab=section");
  await page.getByTestId("shape-circle").click();
  const dims = page.getByTestId("dimension-fields");
  await expect(dims.getByTestId("field-radius")).toBeVisible();
  await expect(dims.getByTestId("field-width")).toHaveCount(0);
  await expect(dims.getByTestId("field-web_thickness")).toHaveCount(0);

  // r = 50 mm: A = π r² = 78.54 cm²
  await page.getByTestId("field-radius").fill("50");
  await expect(page.getByTestId("result-area")).toContainText("78.54");
  await expect(page.getByTestId("section-drawing")).toBeVisible();
  await expect(page.getByTestId("marker-centroid")).toBeVisible();
  await expect(page.getByTestId("dim-width")).toHaveText("100 mm");

  await page.getByTestId("shape-i_beam").click();
  await expect(dims.getByTestId("field-web_thickness")).toBeVisible();
  await expect(dims.getByTestId("field-radius")).toHaveCount(0);
});

test("propped cantilever with a central point load: reactions 11P/16 and 5P/16", async () => {
  await page.goto("./#/structural?tab=beam");
  await page.getByTestId("left_support-fixed").click();
  await page.getByTestId("right_support-pinned").click();
  await page.getByTestId("field-length").fill("4");
  await page.getByTestId("load-0-kind").selectOption("point");
  await page.getByTestId("load-0-value").fill("16"); // P = 16 kN
  await page.getByTestId("load-0-x").fill("2"); // L / 2

  const det = page.getByTestId("determinacy");
  await expect(det).toHaveAttribute("data-status", "indeterminate");
  await expect(det).toHaveAttribute("data-degree", "1");

  // FBD drawn from the inputs
  const fbd = page.getByTestId("fbd");
  await expect(fbd).toBeVisible();
  await expect(fbd.getByTestId("support-left-fixed")).toHaveCount(1);
  await expect(fbd.getByTestId("support-right-pinned")).toHaveCount(1);
  await expect(fbd.getByTestId("fbd-point")).toHaveCount(1);

  await page.getByTestId("calculate").click();
  await expect(page.getByTestId("result-Ay").locator(".font-mono")).toHaveText("11 kN"); // 11P/16
  await expect(page.getByTestId("result-By").locator(".font-mono")).toHaveText("5 kN"); // 5P/16
  await expect(page.getByTestId("result-MA").locator(".font-mono")).toHaveText("12 kN·m"); // 3PL/16
  await expect(page.getByTestId("run-error")).toHaveCount(0);

  // reactions appear on the FBD, and the four diagrams render
  await expect(fbd.getByTestId("fbd-reaction")).toHaveCount(2);
  await expect(fbd.getByTestId("fbd-reaction-moment")).toHaveCount(1);
  for (const id of ["deflection", "slope", "shear", "moment"]) {
    await expect(page.locator(`[data-testid="chart-${id}"] .main-svg`).first()).toBeVisible();
  }

  // the link reproduces the beam
  const url = page.url();
  await page.goto("./#/");
  await page.goto(url);
  await expect(page.getByTestId("result-By").locator(".font-mono")).toHaveText("5 kN");
});

test("a mechanism is flagged and not solved", async () => {
  await page.goto("./#/structural?tab=beam");
  await page.getByTestId("left_support-pinned").click();
  await page.getByTestId("right_support-free").click();
  await expect(page.getByTestId("determinacy")).toHaveAttribute("data-status", "mechanism");
  await expect(page.getByTestId("calculate")).toBeDisabled();
});
