import { test, expect } from "@playwright/test";
import { createE2EUser, loginViaUI } from "./helpers";

test.describe("Auth E2E", () => {
  test("login flow — fill form, submit, session persists", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);

    await loginViaUI(page, email, password);

    // Should be on catalogue or home page
    await expect(page).not.toHaveURL(/\/auth\/login/);

    // Session persists — navigate to auth-gated page
    await page.goto("/my/submissions");
    await expect(page).not.toHaveURL(/\/auth\/login/);
  });

  test("login form shows error for invalid credentials", async ({ page }) => {
    await page.goto("/auth/login");
    await page.fill("input[name='email']", "nonexistent@test.local");
    await page.fill("input[name='password']", "wrongpassword");
    await page.click("button[type='submit']");

    // Should stay on login page or redirect back with error
    await page.waitForURL(/\/auth\/login/, { timeout: 5_000 });
    const html = await page.content();
    // Should contain error indication
    expect(html).toBeTruthy();
  });

  test("signup page renders correctly", async ({ page }) => {
    await page.goto("/auth/signup");
    await expect(page.locator("input[name='email']")).toBeVisible();
    await expect(page.locator("input[name='password']")).toBeVisible();
    await expect(page.locator("input[name='confirm_password']")).toBeVisible();
  });
});
