import { test, expect } from "@playwright/test";
import { createE2EUser, loginViaUI } from "./helpers";

test.describe("HTMX Interactions E2E", () => {
  test("search updates results without full page reload", async ({ page }) => {
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
    // Page should NOT have fully reloaded — nav should still be present
    await expect(page.locator("nav")).toBeVisible();
  });

  test("vote click swaps count in-place via HTMX", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);

    // Navigate to a plugin detail page (vote buttons are only on detail pages)
    await page.goto("/");
    const pluginLink = page.locator("a[href^='/plugins/']").first();
    await expect(pluginLink).toBeVisible();
    await pluginLink.click();
    await expect(page).toHaveURL(/\/plugins\//);

    // Find the upvote button on the detail page
    const voteBtn = page.locator("button[hx-post*='vote']").first();
    await expect(voteBtn).toBeVisible();

    // Wait for HTMX to fully process the button (prevents race under parallel workers)
    await page.waitForFunction(() => {
      const btn = document.querySelector("button[hx-post*='vote']");
      return btn && (window as any).htmx && (window as any).htmx.closest(btn, "[hx-post]");
    });

    // Get initial score
    const scoreEl = page.locator("[id^='vote-'] span.text-sm").first();
    const initialScore = await scoreEl.textContent();

    // Click vote and wait for HTMX POST response
    const [voteResp] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/vote") && r.request().method() === "POST",
      ),
      voteBtn.click(),
    ]);
    expect(voteResp.status()).toBeLessThan(500);

    // After HTMX swap, the vote widget should still be present
    await expect(page.locator("button[hx-post*='vote']").first()).toBeVisible();
    // Score should have changed (upvote toggles 0→1 or 1→0)
    const newScore = await page.locator("[id^='vote-'] span.text-sm").first().textContent();
    expect(newScore).not.toBe(initialScore);
  });
});
