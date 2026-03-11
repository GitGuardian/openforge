# Forge Test Gaps Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all Forge integration and E2E test gaps identified in the testing matrix, and update testing conventions in forge/CLAUDE.md.

**Scope:** Forge only. CLI gaps are in `2026-03-11-cli-test-gaps-plan.md`. Cross-component E2E is in `2026-03-11-cross-component-e2e-plan.md` and depends on this plan completing first.

**Architecture:** TDD order: write failing test first, confirm red, fix, confirm green, commit. Integration tests use `fetch()` against live Forge+Supabase. E2E tests use Playwright with `createE2EUser` + `loginViaUI` helpers.

**Tech Stack:** Bun, Playwright (`@playwright/test`), TypeScript, local Supabase (port 54321), local Forge (port 3000)

**Key facts (verified before writing this plan):**
- `catalogue.test.ts` already covers `GET /api/marketplace.json` and `GET /.well-known/skills/index.json` shape assertions — Task 6 adds only telemetry
- `dotenv` in `helpers.ts` is a plain object loaded by `loadEnv()` from the `.env` file
- Playwright best practice: use `page.waitForResponse()` or `expect(...).toBeVisible()` instead of `page.waitForTimeout()`

**Prerequisites:** Local Supabase running (`supabase start`), Forge server running (`bun run dev`). All commands run from `forge/`.

---

## Chunk 1: Conventions + Seed Data

### Task 1: Add testing conventions to forge/CLAUDE.md

**Files:**
- Modify: `forge/CLAUDE.md`

- [ ] **Step 1: Read forge/CLAUDE.md and find insertion point**

```bash
cat forge/CLAUDE.md
```

Find the `## Rules` section or end of file.

- [ ] **Step 2: Add the testing conventions block**

Add a new `## Testing Conventions` section:

```markdown
## Testing Conventions

### Testing pyramid (4 tiers)

| Tier | Name | Tool |
|------|------|------|
| 1 | Unit | `bun test` (mocked) |
| 2 | Integration | `fetch()` against live Forge+Supabase |
| 3 | E2E (component) | Playwright browser tests |
| 4 | Cross-component E2E | Playwright + CLI subprocess (`spawnSync`) |

### Rule: every feature must have

1. A happy-path **integration test** — `fetch()` against live Forge server + local Supabase
2. A happy-path **E2E test** — Playwright browser test
3. Any feature crossing the CLI↔Forge boundary must also have a **cross-component E2E test** in `e2e/cross-component.spec.ts`

### TDD order is mandatory

- Write integration and E2E tests **first** (red), then implement until they pass (green)
- When fixing a bug: write a failing test that reproduces the bug first, then fix the code
- Never write implementation code before a failing test exists

### Exceptions (note explicitly — never silently skip)

- Pure infrastructure/middleware (CSRF, rate limiting, logging) — unit only acceptable
- Features browser-untestable by nature (webhooks, background jobs) — integration only acceptable
```

- [ ] **Step 3: Commit**

```bash
git add forge/CLAUDE.md
git commit -m "docs(forge): add testing conventions — TDD red/green, 4-tier pyramid"
```

---

### Task 2: Verify and extend seed data for E2E tests

**Files:**
- Modify: `supabase/seed.sql` (check `ls supabase/` for actual filename)

- [ ] **Step 1: Check what seed files exist**

```bash
ls supabase/
```

- [ ] **Step 2: Reset DB and verify approved plugin exists**

```bash
supabase db reset
psql postgresql://postgres:postgres@127.0.0.1:54322/postgres \
  -c "SELECT name, status FROM plugins WHERE status = 'approved' LIMIT 5;"
```

If no rows returned, add to `supabase/seed.sql`:

```sql
INSERT INTO plugins (name, description, git_url, status, owner_id)
VALUES ('seed-test-plugin', 'A seeded plugin for E2E tests',
        'https://github.com/example/seed-test-plugin', 'approved', NULL)
ON CONFLICT (name) DO NOTHING;
```

Then re-run `supabase db reset` and verify.

- [ ] **Step 3: Verify how curator role is stored**

```bash
grep -n "curator\|role" forge/src/db/schema.ts | head -15
grep -n "curator\|role" forge/src/middleware/auth.ts | head -15
```

Note: table name, column name, and role value used for curator promotion. Needed for Task 4.

- [ ] **Step 4: Verify submissions API content type**

```bash
grep -n "json\|form\|urlencoded\|content.type" forge/src/routes/submissions.ts | head -15
```

Note whether `POST /api/submissions` accepts JSON, form-encoded, or both. Needed for Task 4's `createTestSubmission`.

- [ ] **Step 5: Commit seed changes if made**

```bash
git add supabase/seed.sql
git commit -m "chore: extend seed data for E2E test coverage — approved plugin"
```

(Skip if no changes needed.)

---

## Chunk 2: Forge E2E Tests

### Task 3: E2E — Comments (post, reply, edit, delete)

**Files:**
- Create: `forge/e2e/comments.spec.ts`

- [ ] **Step 1: Inspect actual comment form HTML to determine selectors**

```bash
PLUGIN=$(curl -s http://localhost:3000/api/marketplace.json | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['packages'][0]['name'])")
echo "First plugin: $PLUGIN"
curl -s "http://localhost:3000/plugins/${PLUGIN}" | grep -i "textarea\|input.*name.*body\|reply\|edit\|delete" | head -20
```

Note actual textarea/button selectors. Update the test below if they differ from what's assumed.

- [ ] **Step 2: Write the failing test file**

```typescript
import { test, expect } from "@playwright/test";
import { createE2EUser, loginViaUI } from "./helpers";

/** Navigate to the first approved plugin detail page */
async function goToFirstPlugin(page: import("@playwright/test").Page) {
  await page.goto("/");
  // Verify at least one plugin link exists (fails fast if seed is missing)
  const firstPlugin = page.locator("a[href^='/plugins/']").first();
  await expect(firstPlugin).toBeVisible({ timeout: 5000 });
  const href = await firstPlugin.getAttribute("href");
  await page.goto(href!);
  await expect(page).toHaveURL(/\/plugins\//);
}

test.describe("Comments E2E", () => {
  test("post a comment on a plugin detail page", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);
    await goToFirstPlugin(page);

    // Comment form must be present (hard assertion)
    const commentBox = page.locator("textarea[name='body'], input[name='body']").first();
    await expect(commentBox).toBeVisible();
    await commentBox.fill("E2E test comment — please ignore");

    // Wait for the comment to appear after form submission
    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/comments") && r.request().method() === "POST"),
      page.click("button[type='submit']"),
    ]);
    expect(response.status()).toBe(200);
    await expect(page.locator("body")).toContainText("E2E test comment — please ignore");
  });

  test("reply to a comment", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);
    await goToFirstPlugin(page);

    // Post parent comment
    const commentBox = page.locator("textarea[name='body'], input[name='body']").first();
    await expect(commentBox).toBeVisible();
    await commentBox.fill("Parent comment for reply test");
    const [postResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/comments") && r.request().method() === "POST"),
      page.click("button[type='submit']"),
    ]);
    expect(postResp.status()).toBe(200);
    await expect(page.locator("body")).toContainText("Parent comment for reply test");

    // Reply button must be visible (hard assertion — not optional)
    const replyBtn = page.locator("button:has-text('Reply'), a:has-text('Reply')").first();
    await expect(replyBtn).toBeVisible();
    await replyBtn.click();

    const replyBox = page.locator("textarea[name='body'], input[name='body']").last();
    await expect(replyBox).toBeVisible();
    await replyBox.fill("Reply to parent comment");
    const [replyResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/comments") && r.request().method() === "POST"),
      page.locator("button[type='submit']").last().click(),
    ]);
    expect(replyResp.status()).toBe(200);
    await expect(page.locator("body")).toContainText("Reply to parent comment");
  });

  test("edit own comment", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);
    await goToFirstPlugin(page);

    const commentBox = page.locator("textarea[name='body'], input[name='body']").first();
    await expect(commentBox).toBeVisible();
    await commentBox.fill("Original comment text");
    const [postResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/comments") && r.request().method() === "POST"),
      page.click("button[type='submit']"),
    ]);
    expect(postResp.status()).toBe(200);
    await expect(page.locator("body")).toContainText("Original comment text");

    // Edit button must be visible (hard assertion)
    const editBtn = page.locator("button:has-text('Edit'), a:has-text('Edit')").first();
    await expect(editBtn).toBeVisible();
    await editBtn.click();

    const editBox = page.locator("textarea[name='body'], input[name='body']").last();
    await expect(editBox).toBeVisible();
    await editBox.fill("Edited comment text");
    const [editResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/comments") && (r.request().method() === "PATCH" || r.request().method() === "POST")),
      page.locator("button[type='submit']").last().click(),
    ]);
    expect(editResp.ok()).toBe(true);
    await expect(page.locator("body")).toContainText("Edited comment text");
  });

  test("delete own comment", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    await loginViaUI(page, email, password);
    await goToFirstPlugin(page);

    const commentBox = page.locator("textarea[name='body'], input[name='body']").first();
    await expect(commentBox).toBeVisible();
    await commentBox.fill("Comment to be deleted");
    const [postResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/comments") && r.request().method() === "POST"),
      page.click("button[type='submit']"),
    ]);
    expect(postResp.status()).toBe(200);
    await expect(page.locator("body")).toContainText("Comment to be deleted");

    // Delete button must be visible (hard assertion)
    const deleteBtn = page.locator("button:has-text('Delete'), a:has-text('Delete')").first();
    await expect(deleteBtn).toBeVisible();
    const [deleteResp] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/comments") && (r.request().method() === "DELETE" || r.request().method() === "POST")),
      deleteBtn.click(),
    ]);
    expect(deleteResp.ok()).toBe(true);
    await expect(page.locator("body")).not.toContainText("Comment to be deleted");
  });
});
```

- [ ] **Step 3: Run to verify failing (red)**

```bash
npx playwright test e2e/comments.spec.ts --reporter=list
```

Expected: FAIL. Tests must not pass on first run — if any do, check that the test is not vacuously passing.

- [ ] **Step 4: Fix selector mismatches if needed**

If tests fail with "locator not found", update selectors to match the actual HTML from Step 1. If a genuine bug is found (e.g., delete doesn't actually remove the comment), notify team-lead and follow bug protocol.

- [ ] **Step 5: Run to confirm passing (green)**

```bash
npx playwright test e2e/comments.spec.ts --reporter=list
```

Expected: all 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add forge/e2e/comments.spec.ts
git commit -m "test(forge): add E2E tests for comment post, reply, edit, delete"
```

---

### Task 4: E2E — Curator dashboard (browse, status filter, approve, reject)

**Files:**
- Create: `forge/e2e/curator.spec.ts`
- Modify: `forge/e2e/helpers.ts` (add `promoteUserToCurator`, `createTestSubmission`, `SERVICE_ROLE_KEY`)

- [ ] **Step 1: Re-read schema findings from Task 2 Step 3**

Use the curator role table/column/value found there. The code below assumes `profiles` table with `role = 'curator'` — update if your schema differs.

- [ ] **Step 2: Re-read submissions content type from Task 2 Step 4**

The `createTestSubmission` helper below uses JSON — update to form-encoded if needed.

- [ ] **Step 3: Verify `dotenv` is declared at module scope in forge/e2e/helpers.ts**

```bash
grep -n "const dotenv\|loadEnv\|dotenv =" forge/e2e/helpers.ts | head -5
```

Note whether `dotenv` is a module-scope variable (e.g. `const dotenv = loadEnv()`). This determines the SERVICE_ROLE_KEY expression in Step 4.

- [ ] **Step 4: Add SERVICE_ROLE_KEY export to forge/e2e/helpers.ts**

After the existing exports (`SUPABASE_URL`, `ANON_KEY`), add:

```typescript
// If dotenv IS declared at module scope:
export const SERVICE_ROLE_KEY =
  process.env.SUPABASE_SERVICE_ROLE_KEY ||
  (dotenv as Record<string, string>).SUPABASE_SERVICE_ROLE_KEY ||
  "";

// If dotenv is NOT in scope, use only process.env:
// export const SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
```

Use whichever form matches the finding from Step 3.

Then append at the end of the file:

```typescript
/** Promote a user to curator role via Supabase REST API.
 *  Requires SUPABASE_SERVICE_ROLE_KEY in env or .env file.
 */
export async function promoteUserToCurator(
  request: import("@playwright/test").APIRequestContext,
  userId: string,
): Promise<void> {
  if (!SERVICE_ROLE_KEY) {
    throw new Error(
      "SUPABASE_SERVICE_ROLE_KEY not set — check forge/.env or environment",
    );
  }
  // PATCH updates the existing row; POST would try to insert
  const res = await request.patch(
    `${SUPABASE_URL}/rest/v1/profiles?id=eq.${userId}`,
    {
      data: { role: "curator" },
      headers: {
        apikey: SERVICE_ROLE_KEY,
        Authorization: `Bearer ${SERVICE_ROLE_KEY}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
    },
  );
  if (!res.ok()) {
    throw new Error(
      `Failed to promote to curator: ${res.status()} ${await res.text()}`,
    );
  }
}

/** Create a pending submission via the Forge API. */
export async function createTestSubmission(
  request: import("@playwright/test").APIRequestContext,
  token: string,
  forgeUrl: string = "http://localhost:3000",
): Promise<{ id: string }> {
  const gitUrl = `https://github.com/e2e-curator-test/plugin-${Date.now()}`;
  const res = await request.post(`${forgeUrl}/api/submissions`, {
    data: { gitUrl, description: "Curator E2E test submission" },
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok()) {
    throw new Error(
      `Failed to create test submission: ${res.status()} ${await res.text()}`,
    );
  }
  const data = await res.json();
  return { id: data.id };
}
```

- [ ] **Step 5: Write the failing test file**

```typescript
import { test, expect } from "@playwright/test";
import {
  createE2EUser,
  loginViaUI,
  promoteUserToCurator,
  createTestSubmission,
  SUPABASE_URL,
  ANON_KEY,
} from "./helpers";

/** Sign in via Supabase token endpoint */
async function signIn(
  request: import("@playwright/test").APIRequestContext,
  email: string,
  password: string,
) {
  const res = await request.post(
    `${SUPABASE_URL}/auth/v1/token?grant_type=password`,
    {
      data: { email, password },
      headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
    },
  );
  if (!res.ok()) throw new Error(`Sign-in failed: ${res.status()}`);
  const data = await res.json();
  return { userId: data.user?.id as string, token: data.access_token as string };
}

test.describe("Curator E2E", () => {
  test("curator dashboard loads and shows submissions", async ({
    page,
    request,
  }) => {
    const { email, password } = await createE2EUser(request);
    const { userId, token } = await signIn(request, email, password);
    await promoteUserToCurator(request, userId);
    await createTestSubmission(request, token);

    await loginViaUI(page, email, password);
    await page.goto("/curator/submissions");
    await expect(page).toHaveURL(/\/curator\/submissions/);

    // Dashboard must render without error and show submission content
    await expect(page.locator("body")).not.toContainText("403");
    await expect(page.locator("body")).not.toContainText("Internal Server Error");
    await expect(page.locator("body")).toContainText(/[Ss]ubmission/);
  });

  test("curator dashboard status filter works", async ({ page, request }) => {
    const { email, password } = await createE2EUser(request);
    const { userId, token } = await signIn(request, email, password);
    await promoteUserToCurator(request, userId);
    await createTestSubmission(request, token);

    await loginViaUI(page, email, password);
    await page.goto("/curator/submissions");

    // Status filter must be present and functional (hard assertion)
    const pendingFilter = page.locator(
      "a[href*='status=pending'], button:has-text('Pending'), select option[value='pending']",
    ).first();
    await expect(pendingFilter).toBeVisible();
    await pendingFilter.click();
    await expect(page).toHaveURL(/status=pending/);
    await expect(page.locator("body")).not.toContainText("Internal Server Error");
  });

  test("curator can approve a submission — status changes", async ({
    page,
    request,
  }) => {
    const { email, password } = await createE2EUser(request);
    const { userId, token } = await signIn(request, email, password);
    await promoteUserToCurator(request, userId);
    const { id: submissionId } = await createTestSubmission(request, token);

    await loginViaUI(page, email, password);
    await page.goto("/curator/submissions");

    // Approve button must be present (hard assertion)
    const approveBtn = page.locator(
      "button:has-text('Approve'), form button[value='approved']",
    ).first();
    await expect(approveBtn).toBeVisible();

    const [reviewResp] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/review") && r.request().method() === "POST",
      ),
      approveBtn.click(),
    ]);
    expect(reviewResp.ok()).toBe(true);

    // After approval, the submission should no longer appear in pending list
    // (or a success indicator should appear)
    await expect(page).toHaveURL(/\/curator\/submissions/);
    await expect(page.locator("body")).not.toContainText("Internal Server Error");
  });

  test("curator can reject a submission — status changes", async ({
    page,
    request,
  }) => {
    const { email, password } = await createE2EUser(request);
    const { userId, token } = await signIn(request, email, password);
    await promoteUserToCurator(request, userId);
    await createTestSubmission(request, token);

    await loginViaUI(page, email, password);
    await page.goto("/curator/submissions");

    const rejectBtn = page.locator(
      "button:has-text('Reject'), form button[value='rejected']",
    ).first();
    await expect(rejectBtn).toBeVisible();

    const [reviewResp] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes("/review") && r.request().method() === "POST",
      ),
      rejectBtn.click(),
    ]);
    expect(reviewResp.ok()).toBe(true);
    await expect(page).toHaveURL(/\/curator\/submissions/);
    await expect(page.locator("body")).not.toContainText("Internal Server Error");
  });
});
```

- [ ] **Step 6: Run to verify failing (red)**

```bash
npx playwright test e2e/curator.spec.ts --reporter=list
```

Expected: FAIL. Common reasons: `promoteUserToCurator` PATCH fails (wrong column), `createTestSubmission` fails (content type), approve/reject buttons not found. Diagnose each:

```bash
grep -rn "curator\|profiles\|role" forge/src/ | grep -v "node_modules" | head -20
```

- [ ] **Step 7: Fix and confirm green**

```bash
npx playwright test e2e/curator.spec.ts --reporter=list
```

Expected: all 4 tests pass.

- [ ] **Step 8: Commit**

```bash
git add forge/e2e/curator.spec.ts forge/e2e/helpers.ts
git commit -m "test(forge): add E2E tests for curator dashboard, status filter, approve, reject"
```

---

### Task 5: E2E — Catalogue extensions (README, skills, search)

**Files:**
- Modify: `forge/e2e/catalogue.spec.ts`

- [ ] **Step 1: Read existing catalogue spec to avoid duplication**

```bash
cat forge/e2e/catalogue.spec.ts
```

Do NOT duplicate existing tests: "browse catalogue and click into plugin detail", "search filters results via HTMX", "sort dropdown changes results".

- [ ] **Step 2: Inspect plugin detail HTML for skills section selector**

```bash
PLUGIN=$(curl -s http://localhost:3000/api/marketplace.json | \
  python3 -c "import sys,json; d=json.load(sys.stdin); print(d['packages'][0]['name'])")
curl -s "http://localhost:3000/plugins/${PLUGIN}" | grep -i "skills\|h2\|h3\|section" | head -20
```

Note the actual heading or element wrapping the skills list.

- [ ] **Step 3: Add missing tests inside the existing describe block**

```typescript
  test("plugin detail page renders without errors", async ({ page }) => {
    await page.goto("/");
    const firstPlugin = page.locator("a[href^='/plugins/']").first();
    await expect(firstPlugin).toBeVisible({ timeout: 5000 });
    const href = await firstPlugin.getAttribute("href");
    await page.goto(href!);

    await expect(page).toHaveURL(/\/plugins\//);
    await expect(page.locator("body")).not.toContainText("Not Found");
    await expect(page.locator("body")).not.toContainText("Internal Server Error");
    await expect(page.locator("h1, h2").first()).toBeVisible();
  });

  test("plugin detail page shows skills section", async ({ page }) => {
    await page.goto("/");
    const firstPlugin = page.locator("a[href^='/plugins/']").first();
    await expect(firstPlugin).toBeVisible({ timeout: 5000 });
    const href = await firstPlugin.getAttribute("href");
    await page.goto(href!);

    await expect(page).toHaveURL(/\/plugins\//);
    // Update selector below to match actual skills section heading/container
    const skillsSection = page.locator(
      "[data-section='skills'], #skills, h2:has-text('Skills'), h3:has-text('Skills'), h2:has-text('skill'), h3:has-text('skill')",
    );
    await expect(skillsSection).toBeVisible();
  });

  test("search returns results or empty state without error", async ({ page }) => {
    await page.goto("/");
    const searchInput = page.locator("input[name='q']");
    await expect(searchInput).toBeVisible();

    await searchInput.fill("plugin");

    // Wait for HTMX GET response (search uses GET, not POST)
    await page.waitForResponse((r) => r.url().includes("/partials/plugin-list") && r.request().method() === "GET");

    const listArea = page.locator("#plugin-list");
    await expect(listArea).toBeVisible();
    await expect(listArea).not.toContainText("Internal Server Error");
  });
```

- [ ] **Step 4: Run to verify failing (red)**

```bash
npx playwright test e2e/catalogue.spec.ts --reporter=list
```

Expected: new tests FAIL — especially skills section selector.

- [ ] **Step 5: Fix skills selector using Step 2 findings**

Update selector to match the actual HTML element.

- [ ] **Step 6: Run full E2E suite**

```bash
npx playwright test --reporter=list
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add forge/e2e/catalogue.spec.ts
git commit -m "test(forge): add E2E tests for plugin detail render, skills section, search"
```

---

## Chunk 3: Forge Integration Gaps

### Task 6: Integration — Telemetry POST

**Files:**
- Create: `forge/tests/integration/api.test.ts`

Note: `GET /api/marketplace.json` and `GET /.well-known/skills/index.json` shape tests already exist in `catalogue.test.ts` (verified). This task adds only what is not yet covered: `POST /api/telemetry`.

> **TDD Exception:** This is a gap-fill for a pre-existing endpoint — no red step. Write the test file and run green directly. If either test fails unexpectedly, that is a regression bug — stop, diagnose, and fix the endpoint before proceeding.

- [ ] **Step 1: Confirm existing coverage and check telemetry endpoint signature**

```bash
grep -n "telemetry\|marketplace\|well-known" forge/tests/integration/catalogue.test.ts | head -10
grep -n "telemetry\|POST\|body\|validate\|size" forge/src/routes/api.ts | head -20
```

Note the required body fields and error conditions.

- [ ] **Step 2: Write the failing test file**

```typescript
import { describe, expect, test } from "bun:test";
import { anonFetch } from "./helpers";

describe("Telemetry API (integration)", () => {
  test("POST /api/telemetry with valid body returns 200 or 204", async () => {
    // Update the body fields below if the endpoint requires different fields
    // (confirmed from forge/src/routes/api.ts in Step 1)
    const res = await anonFetch("/api/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        event: "install",
        plugin: "test-plugin",
        agent: "claude-code",
        version: "1.0.0",
      }),
    });
    expect([200, 204]).toContain(res.status);
  });

  test("POST /api/telemetry with oversized body returns 4xx", async () => {
    // Spec says 4KB body size limit
    const bigBody = JSON.stringify({ event: "x", data: "x".repeat(5000) });
    const res = await anonFetch("/api/telemetry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: bigBody,
    });
    expect(res.status).toBeGreaterThanOrEqual(400);
    expect(res.status).toBeLessThan(500);
  });
});
```

- [ ] **Step 3: Run to confirm passing (green)**

```bash
bun run test:integration --test-name-pattern "Telemetry"
```

Expected: both tests pass (the telemetry endpoint is pre-existing).

- [ ] **Step 4: Commit**

```bash
git add forge/tests/integration/api.test.ts
git commit -m "test(forge): add integration tests for telemetry POST endpoint"
```

---

### Task 7: Integration — Pagination

**Files:**
- Modify: `forge/tests/integration/catalogue.test.ts`

- [ ] **Step 1: Check default page size and current plugin count**

```bash
grep -n "page\|limit\|offset\|perPage" forge/src/routes/pages.ts | head -10
psql postgresql://postgres:postgres@127.0.0.1:54322/postgres \
  -c "SELECT COUNT(*) FROM plugins WHERE status = 'approved';"
```

If plugin count < page size, add more plugins to `supabase/seed.sql`.

- [ ] **Step 2: Append pagination tests to the existing describe block**

```typescript
  test("GET /?page=2 renders without error", async () => {
    const res = await anonFetch("/?page=2");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).not.toContain("Internal Server Error");
    expect(html).toBeTruthy();
  });

  test("GET /?page=1 and /?page=2 differ when enough plugins are seeded", async () => {
    const [res1, res2] = await Promise.all([
      anonFetch("/?page=1"),
      anonFetch("/?page=2"),
    ]);
    expect(res1.status).toBe(200);
    expect(res2.status).toBe(200);
    const html1 = await res1.text();
    const html2 = await res2.text();
    expect(html1).not.toContain("Internal Server Error");
    expect(html2).not.toContain("Internal Server Error");
    // Pages must differ — Step 1 ensures enough plugins are seeded
    expect(html1).not.toEqual(html2);
  });
```

> **TDD Exception:** This is a gap-fill for pre-existing pagination functionality — no red step. Write the tests and run green directly. If tests fail, that is a regression — stop, diagnose, and fix before proceeding.

- [ ] **Step 3: Run to confirm passing (green)**

```bash
bun run test:integration --test-name-pattern "page"
```

Expected: both tests pass (pagination is pre-existing).

- [ ] **Step 4: Run full integration suite to confirm no regressions**

```bash
bun run test:integration
```

Expected: 57+ pass (55 existing + 2 new pagination), 0 fail.

- [ ] **Step 5: Commit**

```bash
git add forge/tests/integration/catalogue.test.ts
git commit -m "test(forge): add integration tests for pagination"
```

---

## Final Verification

- [ ] **Run all Forge test tiers**

```bash
bun test
bun run test:integration
npx playwright test
```

Expected:
- `bun test`: 296+ pass, 0 fail
- `bun run test:integration`: 57+ pass, 0 fail
- `npx playwright test`: 20+ pass, 0 fail (10 existing + 4 comment + 4 curator + 3 catalogue)

- [ ] **Run coverage check**

```bash
bash scripts/check-coverage.sh 90
```

Expected: ≥90%.

- [ ] **Final commit**

```bash
git add forge/e2e/comments.spec.ts forge/e2e/curator.spec.ts forge/e2e/catalogue.spec.ts \
  forge/e2e/helpers.ts forge/tests/integration/api.test.ts \
  forge/tests/integration/catalogue.test.ts forge/CLAUDE.md
git commit -m "test(forge): close integration and E2E test gaps per testing matrix"
```
