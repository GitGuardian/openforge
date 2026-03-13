import { test, expect } from "@playwright/test";
import { createE2EUser, resetRateLimits } from "./helpers";

test.describe("Rate limiting", () => {
  test.beforeAll(async ({ request }) => {
    await resetRateLimits(request);
  });

  test("login returns 429 after exceeding rate limit for same email", async ({
    page,
    request,
  }) => {
    const { email } = await createE2EUser(request);

    // Make 5 login attempts (the limit) — all should get through
    for (let i = 0; i < 5; i++) {
      await page.goto("/auth/login");
      await page.fill("input[name='email']", email);
      await page.fill("input[name='password']", "wrong-password");
      await page.click("button[type='submit']");
      // Should redirect to login with error (not 429)
      await page.waitForURL(/\/auth\/login\?error=/, { timeout: 5_000 });
    }

    // 6th attempt should be rate limited — intercept the response
    const [response] = await Promise.all([
      page.waitForResponse((res) => res.url().includes("/auth/login") && res.request().method() === "POST"),
      (async () => {
        await page.goto("/auth/login");
        await page.fill("input[name='email']", email);
        await page.fill("input[name='password']", "wrong-password");
        await page.click("button[type='submit']");
      })(),
    ]);

    expect(response.status()).toBe(429);
  });

  test("signup returns 429 after exceeding rate limit for same email", async ({
    page,
    request,
  }) => {
    await resetRateLimits(request);
    const uniqueEmail = `rate-limit-signup-${Date.now()}@test.local`;

    // Make 3 signup attempts (the limit)
    for (let i = 0; i < 3; i++) {
      await page.goto("/auth/signup");
      await page.fill("input[name='email']", uniqueEmail);
      await page.fill("input[name='password']", "test-password-123!");
      await page.fill("input[name='confirm_password']", "test-password-123!");
      await page.click("button[type='submit']");
      await page.waitForLoadState("networkidle");
    }

    // 4th attempt should be rate limited
    const [response] = await Promise.all([
      page.waitForResponse((res) => res.url().includes("/auth/signup") && res.request().method() === "POST"),
      (async () => {
        await page.goto("/auth/signup");
        await page.fill("input[name='email']", uniqueEmail);
        await page.fill("input[name='password']", "test-password-123!");
        await page.fill("input[name='confirm_password']", "test-password-123!");
        await page.click("button[type='submit']");
      })(),
    ]);

    expect(response.status()).toBe(429);
  });

  test("different emails from same IP are rate-limited independently", async ({
    page,
    request,
  }) => {
    await resetRateLimits(request);

    const user1 = await createE2EUser(request);
    const user2 = await createE2EUser(request);

    // Exhaust rate limit for user1 (5 attempts)
    for (let i = 0; i < 5; i++) {
      await page.goto("/auth/login");
      await page.fill("input[name='email']", user1.email);
      await page.fill("input[name='password']", "wrong-password");
      await page.click("button[type='submit']");
      await page.waitForURL(/\/auth\/login\?error=/, { timeout: 5_000 });
    }

    // user2 should still be able to login (different bucket)
    await page.goto("/auth/login");
    await page.fill("input[name='email']", user2.email);
    await page.fill("input[name='password']", user2.password);
    await page.click("button[type='submit']");
    await page.waitForURL((url) => !url.pathname.includes("/auth/login"), {
      timeout: 10_000,
    });

    // If we got here, user2 was not rate-limited — the URL should be / (home)
    expect(page.url()).not.toContain("429");
  });
});
