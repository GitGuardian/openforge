import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { test, expect } from "@playwright/test";
import {
  createE2EUser,
  loginViaUI,
  signInAndGetToken,
  promoteUserToCurator,
} from "./helpers";
import { cliLogin, cliPublish } from "./cli-helper";

test.describe("Cross-Component E2E", () => {
  let tmpXdg: string;

  test.beforeEach(() => {
    tmpXdg = mkdtempSync(join(tmpdir(), "openforge-xdg-"));
  });

  test.afterEach(() => {
    try {
      rmSync(tmpXdg, { recursive: true });
    } catch {
      // Ignore cleanup errors
    }
  });

  test("CLI publish → curator approves in browser → submission confirmed", async ({
    page,
    request,
  }) => {
    // 1. Create user via Supabase Auth
    const { email, password } = await createE2EUser(request);
    const { userId } = await signInAndGetToken(request, email, password);

    // 2. Login via browser first (creates app user row)
    await loginViaUI(page, email, password);

    // 3. Promote to curator (user row now exists)
    await promoteUserToCurator(request, userId);

    // 4. CLI login + publish
    const loginResult = cliLogin(email, password, tmpXdg);
    expect(loginResult.exitCode).toBe(0);

    const gitUrl = `https://github.com/e2e-cross-test/plugin-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const publishResult = cliPublish(gitUrl, "Cross-component E2E test", tmpXdg);
    expect(publishResult.exitCode).toBe(0);

    // 5. Navigate to curator dashboard
    await page.goto("/curator/submissions?status=pending");
    await expect(page).toHaveURL(/\/curator\/submissions/);
    await expect(page.locator("body")).not.toContainText("Internal Server Error");

    // Must show at least one submission row
    await expect(page.locator("table tbody tr").first()).toBeVisible();

    // Approve button must be present
    const approveBtn = page.locator("button:text-is('Approve')").first();
    await expect(approveBtn).toBeVisible();

    const [reviewResp] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/review") && r.request().method() === "POST",
      ),
      approveBtn.click(),
    ]);
    expect(reviewResp.ok()).toBe(true);

    const responseText = await reviewResp.text();
    expect(responseText.toLowerCase()).toContain("approved");
  });

  test("CLI publish → curator approves → marketplace.json serves valid data", async ({
    page,
    request,
  }) => {
    // 1. Create user + login via browser (creates user row) + promote
    const { email, password } = await createE2EUser(request);
    const { userId } = await signInAndGetToken(request, email, password);
    await loginViaUI(page, email, password);
    await promoteUserToCurator(request, userId);

    // 2. CLI login + publish
    const loginResult = cliLogin(email, password, tmpXdg);
    expect(loginResult.exitCode).toBe(0);

    const gitUrl = `https://github.com/e2e-cross-test/plugin-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const publishResult = cliPublish(gitUrl, "Cross-component catalogue test", tmpXdg);
    expect(publishResult.exitCode).toBe(0);

    // 3. Approve via curator dashboard
    await page.goto("/curator/submissions?status=pending");
    await expect(page.locator("table tbody tr").first()).toBeVisible();

    const approveBtn = page.locator("button:text-is('Approve')").first();
    await expect(approveBtn).toBeVisible();

    const [reviewResp] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/review") && r.request().method() === "POST",
      ),
      approveBtn.click(),
    ]);
    expect(reviewResp.ok()).toBe(true);

    // 4. Verify marketplace.json still serves valid data after approval
    const marketplaceRes = await request.get(
      "http://localhost:3000/api/marketplace.json",
    );
    expect(marketplaceRes.ok()).toBe(true);
    const marketplace = await marketplaceRes.json();
    expect(marketplace).toHaveProperty("packages");
    expect(Array.isArray(marketplace.packages)).toBe(true);
  });
});
