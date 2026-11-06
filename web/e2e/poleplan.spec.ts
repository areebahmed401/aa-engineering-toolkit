import { expect, test, type Page } from "@playwright/test";

// The pole-plan tab of the structural page: draw a planar system, see the counting criterion, the poles and the mode.

test.describe.configure({ mode: "serial" });

let page: Page;

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  await page.goto("./#/structural?tab=poles");
  await expect(page.locator('[data-testid="engine-status"]').first()).toHaveAttribute("data-stage", "ready", { timeout: 180_000 });
});

test.afterAll(async () => page.close());

/** Screen position of a model point (metres) on the canvas. */
async function at(x: number, y: number) {
  const canvas = page.getByTestId("pole-canvas");
  await canvas.scrollIntoViewIfNeeded();
  const box = (await canvas.boundingBox())!;
  const [cx, cy, scale] = (await canvas.getAttribute("data-view"))!.split(",").map(Number);
  return { x: box.x + box.width / 2 + (x - cx) * scale, y: box.y + box.height / 2 - (y - cy) * scale };
}

async function click(x: number, y: number) {
  const p = await at(x, y);
  await page.mouse.click(p.x, p.y);
}

const verdict = () => page.getByTestId("pole-verdict");

test("old pole plan links open the tab, which starts with the two-hinge beam: movable, one contradiction", async () => {
  await page.goto("./#/tool/structural.pole_plan");
  await expect(page).toHaveURL(/#\/structural\?tab=poles/);
  await expect(page.getByTestId("tab-poles")).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("pole-canvas")).toBeVisible();
  await expect(page.getByTestId("pole-preset")).toHaveValue("two-hinge");
  await expect(verdict()).toContainText("Movable", { timeout: 60_000 });
  await expect(verdict()).toHaveAttribute("data-movable", "true");
  await expect(page.getByTestId("pole-counting")).toContainText("U = (A + z)");
  await expect(page.getByTestId("stat-U")).toContainText("0");
  await expect(page.getByTestId("pole-agree")).toHaveAttribute("data-agree", "true");
  await expect(page.getByTestId("pole-contradiction")).toHaveCount(1);
  await expect(page.getByTestId("contradiction-mark")).toHaveCount(1);
  await expect(page.getByTestId("go-line")).toHaveCount(1);
  await expect(page.getByTestId("body-1")).toHaveAttribute("data-immovable", "true");
  await expect(page.getByTestId("pole-(2,3)")).toBeVisible();
});

test("the four-support beam is immovable", async () => {
  await page.getByTestId("pole-preset").selectOption("two-hinge-four");
  await expect(verdict()).toContainText("Immovable", { timeout: 60_000 });
  await expect(verdict()).toHaveAttribute("data-movable", "false");
  await expect(page.getByTestId("pole-contradiction").first()).toBeVisible();
});

test("the truss with two bands is movable, has the pole (1,2) and a displacement figure", async () => {
  await page.getByTestId("pole-preset").selectOption("truss");
  await expect(verdict()).toHaveAttribute("data-movable", "true", { timeout: 60_000 });
  await expect(verdict()).toContainText(/^Movable/);
  await expect(page.getByTestId("stat-k")).toContainText("4");
  await expect(page.getByTestId("pole-(1,2)")).toBeVisible();
  await expect(page.getByTestId("pole-row-(1,2)")).toBeVisible();
  await expect(page.getByTestId("displacement-figure")).toHaveCount(0);
  await page.getByTestId("toggle-disp").check();
  await expect(page.getByTestId("displacement-figure")).toBeVisible();
  await page.getByTestId("toggle-poles").uncheck();
  await expect(page.getByTestId("pole-(1,2)")).toHaveCount(0);
  await page.getByTestId("toggle-poles").check();
  await page.getByTestId("toggle-disp").uncheck();
});

test("the link reproduces the drawing", async () => {
  await expect(page).toHaveURL(/[?&]i=/); // the truss differs from the default example
  const url = page.url();
  await page.goto("./#/");
  await page.goto(url);
  await expect(page.getByTestId("pole-preset")).toHaveValue("truss");
  await expect(verdict()).toHaveAttribute("data-movable", "true", { timeout: 60_000 });
});

test("draw a small system from scratch: two bars, pin and roller, then a hinge", async () => {
  await page.getByTestId("pole-preset").selectOption("two-hinge");
  await page.getByTestId("pole-clear").click();
  await expect(page.getByTestId("pole-empty")).toBeVisible();
  await page.getByTestId("zoom-fit").click();

  await page.keyboard.press("b");
  await click(2, 0);
  await click(4, 0);
  await click(6, 0);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("member-m1")).toBeAttached();
  await expect(page.getByTestId("member-m2")).toBeAttached();
  await expect(page.getByTestId("pole-empty")).toHaveCount(0);

  await page.getByTestId("tool-pin").click();
  await click(2, 0);
  await page.keyboard.press("r");
  await click(6, 0);
  await expect(page.getByTestId("support-n1-pin")).toBeVisible();
  await expect(page.getByTestId("support-n3-roller")).toBeVisible();
  await expect(page.getByTestId("support-controls")).toContainText("roller");
  await expect(verdict()).toContainText("Immovable", { timeout: 60_000 }); // one welded body on three reactions
  await expect(page.getByTestId("stat-A")).toContainText("3");

  await page.keyboard.press("h");
  await click(4, 0);
  await expect(page.getByTestId("node-n2")).toHaveAttribute("data-joint", "hinge");
  await expect(verdict()).toContainText(/^Movable/, { timeout: 60_000 }); // pin + hinge + roller on a straight line
  await expect(page.getByTestId("stat-k")).toContainText("2");

  // undo the hinge, redo it
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("node-n2")).toHaveAttribute("data-joint", "rigid");
  await expect(verdict()).toContainText("Immovable", { timeout: 60_000 });
  await page.keyboard.press("Control+y");
  await expect(page.getByTestId("node-n2")).toHaveAttribute("data-joint", "hinge");
  await expect(verdict()).toContainText(/^Movable/, { timeout: 60_000 });
});

test("engine errors show in a box: a sleeve needs two collinear bars", async () => {
  await page.getByTestId("tool-sleeve").click();
  await click(2, 0); // end node with a single bar
  await expect(page.getByTestId("run-error")).toBeVisible({ timeout: 60_000 });
  await expect(page.getByTestId("run-error")).toContainText(/sleeve|Sleeve/);
  await page.keyboard.press("Control+z");
  await expect(page.getByTestId("run-error")).toHaveCount(0, { timeout: 60_000 });
});
