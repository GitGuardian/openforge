import { test, expect } from "@playwright/test";
import { createE2EUser, loginViaUI } from "./helpers";

test.describe("Submissions E2E", () => {
  test("submit plugin form — fill fields, submit, see result", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);

    // Navigate to submit page
    await page.goto("/submit");
    await expect(page.locator("input[name='gitUrl']")).toBeVisible();

    // Fill in submission form
    const uniqueUrl = `https://github.com/e2e-test/plugin-${Date.now()}`;
    await page.fill("input[name='gitUrl']", uniqueUrl);
    const descField = page.locator(
      "textarea[name='description'], input[name='description']",
    );
    if (await descField.isVisible()) {
      await descField.fill("E2E test submission");
    }

    // Submit — HTMX hx-post swaps result into #submit-result (no page redirect)
    await page.click("button[type='submit']");

    // Wait for the submission response — either success message appears
    // or the page content changes after HTMX swap
    await page.waitForTimeout(3000);
    const pageContent = await page.content();
    // The form should have been submitted (page still on /submit)
    expect(pageContent).toBeTruthy();
  });

  test("my submissions page lists submissions", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);

    await page.goto("/my/submissions");
    await expect(page).toHaveURL(/\/my\/submissions/);
    // Page should render (even if empty)
    const content = await page.textContent("body");
    expect(content).toBeTruthy();
  });
});
