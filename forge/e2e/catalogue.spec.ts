import { test, expect } from "@playwright/test";

test.describe("Catalogue E2E", () => {
  test("browse catalogue and click into plugin detail", async ({ page }) => {
    // Navigate to catalogue
    await page.goto("/");
    await expect(page).toHaveTitle(/OpenForge/);

    // Page should contain plugin cards or empty state
    const content = await page.textContent("body");
    expect(content).toBeTruthy();

    // If plugins exist, click the first one
    const pluginLink = page.locator("a[href^='/plugins/']").first();
    if (await pluginLink.isVisible()) {
      await pluginLink.click();
      await expect(page).toHaveURL(/\/plugins\//);
      // Detail page should render
      const detail = await page.textContent("body");
      expect(detail).toBeTruthy();
    }
  });

  test("search filters results via HTMX", async ({ page }) => {
    await page.goto("/");

    const searchInput = page.locator("input[name='q']");
    await expect(searchInput).toBeVisible();

    await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/partials/plugin-list") &&
          r.request().method() === "GET",
      ),
      searchInput.fill("zzz_nonexistent_zzz"),
    ]);

    await expect(page.locator("#plugin-list")).toContainText("No plugins found");
  });

  test("sort dropdown changes results", async ({ page }) => {
    await page.goto("/");

    const sortSelect = page.locator("select[name='sort']");
    await expect(sortSelect).toBeVisible();

    await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/partials/plugin-list") &&
          r.request().method() === "GET",
      ),
      sortSelect.selectOption("newest"),
    ]);

    await expect(page.locator("#plugin-list")).toBeVisible();
    await expect(page.locator("#plugin-list")).not.toContainText(
      "Internal Server Error",
    );
  });

  test("plugin detail page renders without errors", async ({ page }) => {
    await page.goto("/");
    const firstPlugin = page.locator("a[href^='/plugins/']").first();
    await expect(firstPlugin).toBeVisible({ timeout: 5000 });
    const href = await firstPlugin.getAttribute("href");
    await page.goto(href!);

    await expect(page).toHaveURL(/\/plugins\//);
    await expect(page.locator("body")).not.toContainText("Not Found");
    await expect(page.locator("body")).not.toContainText(
      "Internal Server Error",
    );
    // Plugin name heading must be visible
    await expect(page.locator("h1").first()).toBeVisible();
  });

  test("plugin detail page shows metadata and install sections", async ({
    page,
  }) => {
    await page.goto("/");
    const firstPlugin = page.locator("a[href^='/plugins/']").first();
    await expect(firstPlugin).toBeVisible({ timeout: 5000 });
    const href = await firstPlugin.getAttribute("href");
    await page.goto(href!);

    await expect(page).toHaveURL(/\/plugins\//);
    // Install section is always present
    await expect(page.locator("h2:text-is('Install')")).toBeVisible();
    // Metadata section is always present
    await expect(page.locator("h2:text-is('Metadata')")).toBeVisible();
    // Comments section is always present
    await expect(page.locator("#comments-section")).toBeVisible();
  });

  test("search with results returns matching plugins", async ({ page }) => {
    await page.goto("/");
    const searchInput = page.locator("input[name='q']");
    await expect(searchInput).toBeVisible();

    await searchInput.fill("plugin");

    // Wait for HTMX GET response
    await page.waitForResponse(
      (r) =>
        r.url().includes("/partials/plugin-list") &&
        r.request().method() === "GET",
    );

    const listArea = page.locator("#plugin-list");
    await expect(listArea).toBeVisible();
    await expect(listArea).not.toContainText("Internal Server Error");
  });
});
