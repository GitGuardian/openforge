import { test, expect } from "@playwright/test";
import {
  createE2EUser,
  loginViaUI,
  signInAndGetToken,
  promoteUserToCurator,
  createTestSubmission,
} from "./helpers";

test.describe("Curator E2E", () => {
  test("curator dashboard loads and shows submissions", async ({
    page,
    request,
  }) => {
    const { email, password } = await createE2EUser(request);
    const { userId, token } = await signInAndGetToken(request, email, password);

    // Login first to create the users table row, then promote
    await loginViaUI(page, email, password);
    await promoteUserToCurator(request, userId);
    await createTestSubmission(request, token);

    await page.goto("/curator/submissions");
    await expect(page).toHaveURL(/\/curator\/submissions/);

    // Dashboard must render without error
    await expect(page.locator("body")).not.toContainText(
      "Internal Server Error",
    );
    // Must show the "Curator Dashboard" heading
    await expect(page.locator("h1")).toContainText("Curator Dashboard");
    // Must have a table with at least one submission row
    await expect(page.locator("table tbody tr").first()).toBeVisible();
  });

  test("curator dashboard status filter works", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    const { userId, token } = await signInAndGetToken(request, email, password);

    await loginViaUI(page, email, password);
    await promoteUserToCurator(request, userId);
    await createTestSubmission(request, token);

    await page.goto("/curator/submissions");

    // "Pending" filter tab must be present
    const pendingTab = page.locator("a[href*='status=pending']").first();
    await expect(pendingTab).toBeVisible();
    await pendingTab.click();
    await expect(page).toHaveURL(/status=pending/);
    await expect(page.locator("body")).not.toContainText(
      "Internal Server Error",
    );
  });

  test("curator can approve a submission", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    const { userId, token } = await signInAndGetToken(request, email, password);

    await loginViaUI(page, email, password);
    await promoteUserToCurator(request, userId);
    await createTestSubmission(request, token);

    await page.goto("/curator/submissions?status=pending");

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

    // After approval, a success indicator should appear in the review div
    const responseText = await reviewResp.text();
    expect(responseText.toLowerCase()).toContain("approved");
  });

  test("curator can reject a submission", async ({ page, request }) => {
    // Register dialog handler for hx-prompt
    page.on("dialog", (dialog) => dialog.accept("E2E rejection reason"));

    const { email, password } = await createE2EUser(request);
    const { userId, token } = await signInAndGetToken(request, email, password);

    await loginViaUI(page, email, password);
    await promoteUserToCurator(request, userId);
    await createTestSubmission(request, token);

    await page.goto("/curator/submissions?status=pending");

    const rejectBtn = page.locator("button:text-is('Reject')").first();
    await expect(rejectBtn).toBeVisible();

    const [reviewResp] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/review") && r.request().method() === "POST",
      ),
      rejectBtn.click(),
    ]);
    expect(reviewResp.ok()).toBe(true);

    // After rejection, a rejection indicator should appear
    const responseText = await reviewResp.text();
    expect(responseText.toLowerCase()).toContain("rejected");
  });
});
