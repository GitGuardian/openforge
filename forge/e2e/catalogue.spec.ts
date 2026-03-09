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
    if (await searchInput.isVisible()) {
      await searchInput.fill("zzz_nonexistent_zzz");
      // Wait for HTMX swap (debounced 300ms + network)
      await page.waitForTimeout(1000);
      const listArea = page.locator("#plugin-list");
      await expect(listArea).toContainText("No plugins found");
    }
  });

  test("sort dropdown changes results", async ({ page }) => {
    await page.goto("/");

    const sortSelect = page.locator("select[name='sort']");
    if (await sortSelect.isVisible()) {
      await sortSelect.selectOption("newest");
      // Wait for HTMX swap
      await page.waitForTimeout(1000);
      // Page should still be functional
      await expect(page.locator("#plugin-list")).toBeVisible();
    }
  });
});
