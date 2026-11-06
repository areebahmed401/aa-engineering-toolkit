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

test("old torsion links open the torsion tab, which shows the section and a twist", async () => {
  await page.goto("./#/tool/structural.torsion");
  await expect(page).toHaveURL(/#\/structural\?tab=torsion/);
  await expect(page.getByTestId("tab-torsion")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("section-drawing")).toBeVisible();
  await expect(page.getByTestId("marker-centroid")).toBeVisible();
  await expect(page.getByTestId("result-twist_deg")).toContainText("°");
  await expect(page.getByTestId("result-tau_sv_max")).toContainText("MPa");
  await expect(page.locator('[data-testid="chart-twist"] .main-svg').first()).toBeVisible();

  // the evaluation point must lie on the member
  await page.getByTestId("field-position").fill("5000");
  await expect(page.getByTestId("torsion-error")).toBeVisible();
  await expect(page.getByTestId("calculate")).toBeDisabled();
});

test("torsion, restrained: fork-fork with a mid-span torque shows the torque split and alpha", async () => {
  await page.goto("./#/"); // unmount so the previous test's inputs do not carry over
  await page.goto("./#/structural?tab=torsion");
  await expect(page.getByTestId("torsion-mode-restrained")).toHaveAttribute("aria-pressed", "true");
  for (const side of ["left", "right"]) {
    const select = page.getByTestId(`torsion-${side}-support`);
    await select.scrollIntoViewIfNeeded();
    await select.selectOption("fork");
  }
  const x = page.getByTestId("torsion-load-0-x");
  await x.scrollIntoViewIfNeeded();
  await x.fill("0.5");
  await expect(page.getByTestId("torsion-beam")).toBeVisible();
  await expect(page.getByTestId("torsion-support-left-fork")).toBeVisible();
  await expect(page.getByTestId("torsion-load")).toHaveCount(1);
  // symmetric fork-fork: T = +100 N·m just right of the left end
  await expect(page.getByTestId("result-T_left")).toContainText("100");
  await expect(page.getByTestId("result-alpha")).toBeVisible();
  await expect(page.getByTestId("result-alpha-hint")).toBeVisible();
  await expect(page.locator('[data-testid="chart-torque"] .main-svg').first()).toBeVisible();
  await expect(page.locator('[data-testid="chart-bimoment"] .main-svg').first()).toBeVisible();

  // both ends free is rejected before calling Python
  await page.getByTestId("torsion-left-support").selectOption("free");
  await page.getByTestId("torsion-right-support").selectOption("free");
  await expect(page.getByTestId("torsion-error")).toContainText("At least one end");
  await expect(page.getByTestId("calculate")).toBeDisabled();
});

test("torsion, free warping: a rectangle from tab 1 lists J_T in the formulary steps", async () => {
  await page.goto("./#/");
  await page.goto("./#/structural?tab=section");
  const rect = page.getByTestId("shape-rectangle");
  await rect.scrollIntoViewIfNeeded();
  await rect.click();
  await page.getByTestId("tab-torsion").click();
  const free = page.getByTestId("torsion-mode-free");
  await free.scrollIntoViewIfNeeded();
  await free.click();
  await expect(page.getByTestId("torsion-mode-hint")).toContainText("Free warping");
  await expect(page.getByTestId("torsion-offcentre")).toBeVisible();
  await expect(page.getByTestId("torsion-steps")).toContainText("J_T");
  await expect(page.getByTestId("result-sigma_w_max")).toHaveCount(0); // no warping stresses when warping is free
  await expect(page.getByTestId("run-error")).toHaveCount(0);
});

test("torsion with the section drawn in tab 5 (open channel) runs without error", async () => {
  await page.goto("./#/");
  await page.goto("./#/structural?tab=torsion");
  const drawn = page.getByTestId("torsion-source-drawn");
  await drawn.scrollIntoViewIfNeeded();
  await drawn.click();
  await expect(page.getByTestId("torsion-drawn-preview")).toBeVisible();
  await expect(page.getByTestId("field-eta3")).toBeVisible(); // the default channel is open
  await expect(page.getByTestId("torsion-steps")).toContainText("Shear centre"); // only the drawn section lists its pole
  await expect(page.getByTestId("run-error")).toHaveCount(0);
  await expect(page.getByTestId("torsion-error")).toHaveCount(0);
});

test("beam tab shows bending stress across the section; cantilever hogs (top in tension at the wall)", async () => {
  await page.goto("./#/"); // unmount the page so the torsion test's inputs do not carry over
  await page.goto("./#/structural?tab=beam");
  await page.getByTestId("left_support-fixed").click();
  await page.getByTestId("right_support-free").click();
  await page.getByTestId("load-0-kind").selectOption("point");
  await page.getByTestId("field-length").fill("4");
  await page.getByTestId("load-0-value").fill("10");
  await page.getByTestId("load-0-x").fill("4"); // tip load
  await page.getByTestId("calculate").click();

  await expect(page.getByTestId("stress-section")).toBeVisible();
  // peak moment is at the fixed end: x = 0, top fibre in tension
  await expect(page.getByTestId("stress-x-readout")).toContainText("x = 0 ");
  await expect(page.getByTestId("stress-top-label")).toContainText("T");
  const atWall = await page.getByTestId("stress-top-value").innerText();
  expect(atWall.startsWith("-")).toBe(false); // tension is positive

  const slider = page.getByTestId("stress-x");
  await slider.fill(String(await slider.getAttribute("max")));
  await expect(page.getByTestId("stress-top-value")).not.toHaveText(atWall);
});

test("shear flow tab: channel plot, shear centre and steps; canvas editing; closed box steps view; link round-trips", async () => {
  await page.goto("./#/"); // unmount the page so earlier tests' inputs do not carry over
  await page.goto("./#/structural?tab=shear");
  await expect(page.getByTestId("tab-shear")).toHaveAttribute("aria-selected", "true");

  // default channel: plot, markers and the formulary steps
  await expect(page.getByTestId("shear-plot")).toBeVisible();
  await expect(page.getByTestId("shear-sc")).toBeVisible();
  await expect(page.getByTestId("shear-steps")).toContainText("J22");
  await expect(page.getByTestId("result-sc")).toContainText("-18.75 mm"); // e = 3 b² / (h + 6 b) behind the web
  await expect(page.getByTestId("run-error")).toHaveCount(0);

  // textbook style: |t| hatched on the outer side of each wall, three arrows per loaded wall, horizontal NA through S
  const plot = page.getByTestId("shear-plot");
  await plot.scrollIntoViewIfNeeded();
  const bb = async (id: string) => (await plot.getByTestId(id).boundingBox())!;
  const [web, webHatch, top, topHatch, bottom, bottomHatch] = [await bb("shear-wall-1"), await bb("shear-hatch-1"), await bb("shear-wall-0"),
    await bb("shear-hatch-0"), await bb("shear-wall-2"), await bb("shear-hatch-2")];
  expect(webHatch.x).toBeLessThan(web.x - 5); // web diagram left of the web (outside the channel)
  expect(webHatch.x + webHatch.width).toBeLessThan(web.x + web.width + 1);
  expect(topHatch.y).toBeLessThan(top.y - 2); // top flange diagram above it
  expect(bottomHatch.y + bottomHatch.height).toBeGreaterThan(bottom.y + bottom.height + 2); // bottom flange diagram below it
  await expect(plot.getByTestId("shear-arrow")).toHaveCount(9);
  const na = plot.getByTestId("shear-na");
  await expect(na).toHaveCount(1);
  const naBox = (await na.locator("line").boundingBox())!;
  expect(naBox.height).toBeLessThan(2); // horizontal
  const sBox = (await plot.getByTestId("shear-centroid").locator("circle").boundingBox())!;
  expect(Math.abs(naBox.y - (sBox.y + sBox.height / 2))).toBeLessThan(2); // through S

  // canvas: add a wall from node 2 to a new grid point on its left
  await page.getByTestId("shear-mode-wall").click();
  await page.getByTestId("shear-node-2").scrollIntoViewIfNeeded(); // mouse clicks need the node inside the viewport
  const box = await page.getByTestId("shear-node-2").locator("circle").boundingBox();
  const cx = box!.x + box!.width / 2;
  const cy = box!.y + box!.height / 2;
  await page.mouse.click(cx, cy);
  await page.mouse.click(cx - 60, cy);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("shear-nodes-table").locator("tbody tr")).toHaveCount(5);
  await expect(page.getByTestId("shear-walls-table").locator("tbody tr")).toHaveCount(4);
  await expect(page.getByTestId("shear-error")).toHaveCount(0);

  // table: delete the node again, which removes its wall
  await page.getByRole("button", { name: "Delete node 4" }).click();
  await expect(page.getByTestId("shear-nodes-table").locator("tbody tr")).toHaveCount(4);
  await expect(page.getByTestId("shear-walls-table").locator("tbody tr")).toHaveCount(3);

  // a disconnected section is flagged before the tool is called
  await page.getByRole("button", { name: "Delete wall 1" }).click();
  await expect(page.getByTestId("shear-error")).toContainText("not connected");
  await expect(page.getByTestId("calculate")).toBeDisabled();

  // preset: closed box, one cell, steps view with t' + t0 = t
  await page.getByTestId("shear-preset").selectOption("closed_box");
  await expect(page.getByTestId("shear-error")).toHaveCount(0);
  await expect(page.getByTestId("result-cells")).toContainText("1");
  await page.getByTestId("shear-view-steps").click();
  await expect(page.getByTestId("shear-steps-panels")).toBeVisible();
  await expect(page.getByTestId("shear-plot-t_cut")).toBeVisible();
  await expect(page.getByTestId("shear-plot-t0")).toBeVisible();
  await expect(page.getByTestId("shear-plot-t_total")).toBeVisible();
  await expect(page.getByTestId("shear-cut").first()).toBeVisible();
  await expect(page.getByTestId("shear-steps")).toContainText("t0 cell 0");

  // the link reproduces the section
  await expect(page).toHaveURL(/i=/);
  const url = page.url();
  await page.goto("./#/");
  await page.goto(url);
  await expect(page.getByTestId("shear-walls-table").locator("tbody tr")).toHaveCount(4);
  await expect(page.getByTestId("result-cells")).toContainText("1");
});
