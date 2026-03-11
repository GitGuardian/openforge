import { test, expect } from "@playwright/test";
import { createE2EUser, loginViaUI } from "./helpers";

/** Navigate to the first approved plugin detail page */
async function goToFirstPlugin(page: import("@playwright/test").Page) {
  await page.goto("/");
  const firstPlugin = page.locator("a[href^='/plugins/']").first();
  await expect(firstPlugin).toBeVisible({ timeout: 5000 });
  const href = await firstPlugin.getAttribute("href");
  await page.goto(href!);
  await expect(page).toHaveURL(/\/plugins\//);
}

/**
 * Fill the main comment form — handles EasyMDE by setting value and
 * syncing to the hidden textarea so HTMX can read it.
 */
async function fillAndSubmitComment(
  page: import("@playwright/test").Page,
  text: string,
) {
  // Set the value via EasyMDE API and sync to textarea
  await page.evaluate((t) => {
    const mde = (window as any).easyMDE;
    if (mde) {
      mde.value(t);
      // EasyMDE keeps the original textarea — sync value to it
      mde.codemirror.save();
    } else {
      const el = document.getElementById("new-comment") as HTMLTextAreaElement;
      if (el) el.value = t;
    }
  }, text);

  // Click the Comment submit button and wait for POST
  const submitBtn = page
    .locator("#comments-section > form button[type='submit']")
    .first();
  await expect(submitBtn).toBeVisible();

  const [response] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.url().includes("/comments") && r.request().method() === "POST",
    ),
    submitBtn.click(),
  ]);
  return response;
}

test.describe("Comments E2E", () => {
  test("post a comment on a plugin detail page", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);
    await goToFirstPlugin(page);

    // Wait for the comment section to load
    await expect(page.locator("#comments-section")).toBeVisible();

    const response = await fillAndSubmitComment(
      page,
      "E2E test comment — please ignore",
    );
    expect(response.status()).toBe(200);
    await expect(page.locator("#comments-list")).toContainText(
      "E2E test comment — please ignore",
    );
  });

  test("reply to a comment", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);
    await goToFirstPlugin(page);
    await expect(page.locator("#comments-section")).toBeVisible();

    // Post parent comment
    const postResp = await fillAndSubmitComment(
      page,
      "Parent comment for reply test",
    );
    expect(postResp.status()).toBe(200);
    await expect(page.locator("#comments-list")).toContainText(
      "Parent comment for reply test",
    );

    // Reload the page so the comment appears in the full DOM with .replies div
    // (HTMX afterbegin insert doesn't include the wrapper <div> with .replies)
    await page.reload();
    await expect(page.locator("#comments-list")).toContainText(
      "Parent comment for reply test",
    );

    // Click Reply toggle on the comment
    const replyToggle = page.locator("#comments-list button:text-is('Reply')").first();
    await expect(replyToggle).toBeVisible();
    await replyToggle.click();

    // Wait for reply textarea to be visible
    const replyTextarea = page.locator("#comments-list .reply-form textarea[name='body']").first();
    await expect(replyTextarea).toBeVisible({ timeout: 3000 });
    await replyTextarea.fill("Reply to parent comment");

    // Submit the reply form
    const replySubmitBtn = page.locator("#comments-list .reply-form button[type='submit']").first();
    const [replyResp] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/comments") && r.request().method() === "POST",
      ),
      replySubmitBtn.click(),
    ]);
    expect(replyResp.status()).toBe(200);
    await expect(page.locator("#comments-list")).toContainText(
      "Reply to parent comment",
    );
  });

  test("edit own comment", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);
    await goToFirstPlugin(page);
    await expect(page.locator("#comments-section")).toBeVisible();

    const postResp = await fillAndSubmitComment(page, "Original comment text");
    expect(postResp.status()).toBe(200);
    await expect(page.locator("#comments-list")).toContainText(
      "Original comment text",
    );

    // Click Edit (hx-get fetches edit form)
    const editBtn = page.locator("button:text-is('Edit')").first();
    await expect(editBtn).toBeVisible();
    const [editFormResp] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/comments") &&
          r.url().includes("/edit") &&
          r.request().method() === "GET",
      ),
      editBtn.click(),
    ]);
    expect(editFormResp.ok()).toBe(true);

    // Wait for edit textarea to appear
    const editBox = page
      .locator("#comments-list textarea[name='body']")
      .first();
    await expect(editBox).toBeVisible();
    await editBox.fill("Edited comment text");

    // Submit the edit (PATCH)
    const [editResp] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/comments") && r.request().method() === "PATCH",
      ),
      page.locator("#comments-list button[type='submit']").first().click(),
    ]);
    expect(editResp.ok()).toBe(true);
    await expect(page.locator("#comments-list")).toContainText(
      "Edited comment text",
    );
  });

  test("delete own comment", async ({ page, request }) => {
    // Register dialog handler early — hx-confirm triggers a browser confirm()
    page.on("dialog", (dialog) => dialog.accept());

    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);
    await goToFirstPlugin(page);
    await expect(page.locator("#comments-section")).toBeVisible();

    const uniqueText = `Delete-me-${Date.now()}`;
    const postResp = await fillAndSubmitComment(page, uniqueText);
    expect(postResp.status()).toBe(200);
    await expect(page.locator("#comments-list")).toContainText(uniqueText);

    // Find the Delete button (only visible on own comments)
    const deleteBtn = page.locator("button:text-is('Delete')").first();
    await expect(deleteBtn).toBeVisible();

    // Get the comment ID from the parent div for later assertion
    const commentDiv = deleteBtn.locator("xpath=ancestor::div[starts-with(@id,'comment-')]").first();
    const commentId = await commentDiv.getAttribute("id");
    expect(commentId).toBeTruthy();

    const [deleteResp] = await Promise.all([
      page.waitForResponse(
        (r) =>
          r.url().includes("/comments") && r.request().method() === "DELETE",
      ),
      deleteBtn.click(),
    ]);
    expect(deleteResp.ok()).toBe(true);

    // The comment div should be removed from DOM (hx-swap="delete")
    await expect(page.locator(`#${commentId}`)).toHaveCount(0, {
      timeout: 5000,
    });
  });
});
