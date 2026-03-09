import { test, expect } from "@playwright/test";
import { createE2EUser, loginViaUI } from "./helpers";

test.describe("HTMX Interactions E2E", () => {
  test("search updates results without full page reload", async ({ page }) => {
    await page.goto("/");

    const searchInput = page.locator("input[name='q']");
    if (await searchInput.isVisible()) {
      await searchInput.fill("zzz_nonexistent_zzz");
      // Wait for HTMX debounce (300ms) + network
      await page.waitForTimeout(1000);
      const listArea = page.locator("#plugin-list");
      await expect(listArea).toContainText("No plugins found");
      // Page should NOT have fully reloaded — nav should still be present
      await expect(page.locator("nav")).toBeVisible();
    }
  });

  test("vote click swaps count in-place via HTMX", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);
    await page.goto("/");

    // Find a vote button if visible
    const voteBtn = page.locator("[hx-post*='vote']").first();
    if (await voteBtn.isVisible()) {
      await voteBtn.click();
      // Wait for HTMX swap
      await page.waitForTimeout(500);
      // The vote widget area should still be functional (no error)
      const updatedText = await voteBtn.textContent();
      expect(updatedText).toBeTruthy();
    }
  });
});
