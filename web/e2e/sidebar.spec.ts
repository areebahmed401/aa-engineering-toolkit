import { expect, test, type Page } from "@playwright/test";

async function load(page: Page, hash: string) {
  await page.goto("./");
  await page.evaluate(() => localStorage.clear());
  await page.goto(`./#${hash}`);
  await expect(page.getByTestId("sidebar-rail").getByRole("button").first()).toBeVisible();
}

async function hoverOpen(page: Page) {
  await page.getByTestId("sidebar-rail").hover();
  await expect(page.getByTestId("sidebar-overlay")).toBeVisible();
}

const expandedState = (page: Page, id: string) => page.getByTestId(`sidebar-section-${id}`).getByRole("button").first();

test.describe("sidebar", () => {
  test("starts as the icon rail; hover opens an overlay without shifting main; leaving closes it", async ({ page }) => {
    await load(page, "/");
    await expect(page.getByTestId("sidebar")).toHaveCount(0);
    const before = await page.getByRole("main").boundingBox();
    await hoverOpen(page);
    const after = await page.getByRole("main").boundingBox();
    expect(after!.x).toBe(before!.x);
    await expect(page.getByTestId("sidebar")).toBeVisible();
    await page.mouse.move(800, 400);
    await expect(page.getByTestId("sidebar-overlay")).toHaveCount(0);
    await expect(page.getByTestId("sidebar-rail")).toBeVisible();
  });

  test("home page opens with every section collapsed", async ({ page }) => {
    await load(page, "/");
    await hoverOpen(page);
    for (const id of ["thermo", "structural", "electrical", "asme"]) {
      await expect(expandedState(page, id)).toHaveAttribute("aria-expanded", "false");
    }
  });

  test("only the current tool's domain is expanded", async ({ page }) => {
    await load(page, "/tool/asme.flat_head");
    await hoverOpen(page);
    await expect(expandedState(page, "asme")).toHaveAttribute("aria-expanded", "true");
    for (const id of ["thermo", "structural", "electrical"]) {
      await expect(expandedState(page, id)).toHaveAttribute("aria-expanded", "false");
    }
  });

  test("structural page expands only Structural", async ({ page }) => {
    await load(page, "/structural?tab=beam");
    await hoverOpen(page);
    await expect(expandedState(page, "structural")).toHaveAttribute("aria-expanded", "true");
    await expect(expandedState(page, "asme")).toHaveAttribute("aria-expanded", "false");
    await expect(expandedState(page, "thermo")).toHaveAttribute("aria-expanded", "false");
  });

  test("sections can be toggled while the panel is open", async ({ page }) => {
    await load(page, "/");
    await hoverOpen(page);
    const header = expandedState(page, "thermo");
    const link = page.getByTestId("sidebar-section-thermo").getByRole("link", { name: "Fluid properties", exact: true });
    await header.click();
    await expect(header).toHaveAttribute("aria-expanded", "true");
    await expect(link).toBeVisible();
    await header.click();
    await expect(link).toBeHidden();
  });

  test("clicking a rail icon opens the panel with that section expanded", async ({ page }) => {
    await load(page, "/tool/asme.flat_head");
    await page.getByTestId("sidebar-rail").getByRole("button", { name: /Structural/i }).click();
    await expect(page.getByTestId("sidebar-overlay")).toBeVisible();
    await expect(expandedState(page, "structural")).toHaveAttribute("aria-expanded", "true");
    await expect(expandedState(page, "asme")).toHaveAttribute("aria-expanded", "true");
    await expect(expandedState(page, "thermo")).toHaveAttribute("aria-expanded", "false");
  });

  test("the current domain's rail icon is highlighted", async ({ page }) => {
    await load(page, "/tool/asme.flat_head");
    await expect(page.getByTestId("sidebar-rail").getByRole("button", { name: /ASME/i })).toHaveAttribute("aria-current", "true");
    await expect(page.getByTestId("sidebar-rail").getByRole("button", { name: /Thermo/i })).not.toHaveAttribute("aria-current", "true");
  });

  test("pin persists across reload and pushes content; unpin returns to the rail", async ({ page }) => {
    await load(page, "/");
    const railMain = await page.getByRole("main").boundingBox();
    await hoverOpen(page);
    await page.getByTestId("sidebar-collapse").click();
    await expect(page.getByTestId("sidebar-rail")).toHaveCount(0);
    await expect(page.getByTestId("sidebar")).toBeVisible();
    await expect(page.getByTestId("sidebar-collapse")).toHaveAttribute("aria-label", "Unpin sidebar");
    await page.mouse.move(800, 400);
    await expect(page.getByTestId("sidebar")).toBeVisible();
    const pinnedMain = await page.getByRole("main").boundingBox();
    expect(pinnedMain!.x).toBeGreaterThan(railMain!.x + 100);
    await page.reload();
    await expect(page.getByTestId("sidebar")).toBeVisible();
    await expect(page.getByTestId("sidebar-rail")).toHaveCount(0);
    await page.getByTestId("sidebar-collapse").click();
    await page.mouse.move(800, 400);
    await expect(page.getByTestId("sidebar")).toHaveCount(0);
    await expect(page.getByTestId("sidebar-rail")).toBeVisible();
  });

  test("search opens sections with matches and clearing returns to the current domain", async ({ page }) => {
    await load(page, "/tool/asme.flat_head");
    await hoverOpen(page);
    const search = page.getByLabel("Search tools");
    await search.fill("beam");
    const link = page.getByTestId("sidebar").getByRole("link", { name: "2 · Beam" });
    await expect(link).toBeVisible();
    await expect(expandedState(page, "structural")).toHaveAttribute("aria-expanded", "true");
    // search text keeps the overlay open when the pointer leaves
    await page.mouse.move(800, 400);
    await page.waitForTimeout(600);
    await expect(page.getByTestId("sidebar-overlay")).toBeVisible();
    await search.fill("");
    await expect(expandedState(page, "structural")).toHaveAttribute("aria-expanded", "false");
    await expect(expandedState(page, "asme")).toHaveAttribute("aria-expanded", "true");
  });

  test("search finds a structural tab link, it navigates and closes the overlay", async ({ page }) => {
    await load(page, "/");
    await hoverOpen(page);
    await page.getByLabel("Search tools").fill("beam");
    await page.getByTestId("sidebar").getByRole("link", { name: "2 · Beam" }).click();
    await expect(page).toHaveURL(/#\/structural\?tab=beam/);
    await expect(page.getByTestId("sidebar-overlay")).toHaveCount(0);
    await page.mouse.move(800, 400);
    await hoverOpen(page);
    await expect(page.getByTestId("sidebar").getByRole("link", { name: "2 · Beam" })).toHaveAttribute("aria-current", "page");
  });

  test("Escape closes the overlay", async ({ page }) => {
    await load(page, "/");
    await hoverOpen(page);
    await page.getByLabel("Search tools").focus();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("sidebar-overlay")).toHaveCount(0);
  });

  test("Ctrl+B toggles the pin, but not while typing", async ({ page }) => {
    await load(page, "/");
    await page.keyboard.press("Control+b");
    await expect(page.getByTestId("sidebar")).toBeVisible();
    await expect(page.getByTestId("sidebar-rail")).toHaveCount(0);
    await page.keyboard.press("Control+b");
    await expect(page.getByTestId("sidebar-rail")).toBeVisible();
    await page.keyboard.press("Control+b");
    await expect(page.getByTestId("sidebar")).toBeVisible();
    await page.getByLabel("Search tools").focus();
    await page.keyboard.press("Control+b");
    await expect(page.getByTestId("sidebar")).toBeVisible();
    await expect(page.getByTestId("sidebar-rail")).toHaveCount(0);
  });
});
