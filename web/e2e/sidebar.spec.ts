import { expect, test } from "@playwright/test";

test.describe("sidebar", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("./");
    await page.evaluate(() => localStorage.clear());
    await page.goto("./#/");
    await expect(page.getByTestId("sidebar")).toBeVisible();
  });

  test("sections collapse and expand", async ({ page }) => {
    const section = page.getByTestId("sidebar-section-thermo");
    const header = section.getByRole("button", { name: /Thermo/i });
    const link = section.getByRole("link", { name: "Fluid properties", exact: true });
    await expect(header).toHaveAttribute("aria-expanded", "true");
    await expect(link).toBeVisible();
    await header.click();
    await expect(header).toHaveAttribute("aria-expanded", "false");
    await expect(link).toBeHidden();
    await header.click();
    await expect(link).toBeVisible();
  });

  test("collapsed rail persists across reload and expands from a section icon", async ({ page }) => {
    await page.getByTestId("sidebar-collapse").click();
    await expect(page.getByTestId("sidebar-rail")).toBeVisible();
    await page.reload();
    await expect(page.getByTestId("sidebar-rail")).toBeVisible();
    await page.getByTestId("sidebar-rail").getByRole("button", { name: /Structural/i }).click();
    await expect(page.getByTestId("sidebar-rail")).toHaveCount(0);
    await expect(page.getByTestId("sidebar-section-structural").getByRole("button", { expanded: true })).toBeVisible();
  });

  test("search finds a structural tab link and it navigates", async ({ page }) => {
    await page.getByLabel("Search tools").fill("beam");
    const link = page.getByTestId("sidebar").getByRole("link", { name: "2 · Beam" });
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL(/#\/structural\?tab=beam/);
    await expect(page.getByTestId("sidebar").getByRole("link", { name: "2 · Beam" })).toHaveAttribute("aria-current", "page");
  });

  test("Ctrl+B toggles the panel, but not while typing", async ({ page }) => {
    await page.keyboard.press("Control+b");
    await expect(page.getByTestId("sidebar-rail")).toBeVisible();
    await page.keyboard.press("Control+b");
    await expect(page.getByTestId("sidebar-rail")).toHaveCount(0);
    await page.getByLabel("Search tools").focus();
    await page.keyboard.press("Control+b");
    await expect(page.getByTestId("sidebar-rail")).toHaveCount(0);
  });
});
