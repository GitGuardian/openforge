# Phase 5: Submissions & Curation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a community submission pipeline and curator review workflow so users can submit plugins via Forge UI or CLI, curators review them, and approved plugins appear in the catalogue.

**Architecture:** New `submissions` table as audit trail. Submissions create plugins with `pending` status. Curators approve/reject via inline UI (steel thread) then dashboard. CLI gets `publish` + `auth` commands. Existing webhook auto-indexing unchanged.

**Tech Stack:** Forge: Bun + Hono + HTMX + Drizzle + Supabase Auth. CLI: Python 3.10 + Typer + httpx.

**Design doc:** `docs/plans/2026-03-09-phase5-submissions-curation-design.md`

---

## Task 1: Submissions table, migration, and RLS

**Owner:** forge-dev
**Files:**
- Modify: `forge/src/db/schema.ts`
- Create: `forge/src/db/migrations/XXXX_add_submissions.sql` (use next sequence number)
- Create: `forge/tests/routes/submissions.test.ts`

### Step 1: Write failing test for submissions API (red)

Create `forge/tests/routes/submissions.test.ts`:

```ts
import { describe, test, expect, mock, beforeEach } from "bun:test";

// Mock db module
const mockDb = {
  insert: mock(() => mockDb),
  values: mock(() => mockDb),
  returning: mock(() => []),
  select: mock(() => mockDb),
  from: mock(() => mockDb),
  where: mock(() => mockDb),
  innerJoin: mock(() => mockDb),
  leftJoin: mock(() => mockDb),
};

mock.module("../../src/db", () => ({
  db: mockDb,
}));

mock.module("../../src/lib/supabase", () => ({
  supabase: { auth: { getUser: mock() } },
}));

import { Hono } from "hono";
import submissions from "../../src/routes/submissions";

function createApp(user: { id: string; role: string } | null = null) {
  const app = new Hono();
  app.use("*", async (c, next) => {
    c.set("user", user);
    await next();
  });
  app.route("/api/submissions", submissions);
  return app;
}

const testUser = { id: "user-1", email: "test@example.com", role: "user", displayName: "Test User", authId: "auth-1" };
const testCurator = { id: "curator-1", email: "curator@example.com", role: "curator", displayName: "Curator", authId: "auth-2" };

describe("POST /api/submissions", () => {
  beforeEach(() => {
    mock.restore();
  });

  test("returns 401 if not authenticated", async () => {
    const app = createApp(null);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://github.com/owner/repo" }),
    });
    expect(res.status).toBe(401);
  });

  test("returns 400 if gitUrl missing", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    expect(res.status).toBe(400);
  });

  test("returns 400 if gitUrl is invalid", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "not-a-url" }),
    });
    expect(res.status).toBe(400);
  });

  test("creates submission and returns 201", async () => {
    const mockSubmission = {
      id: "sub-1",
      gitUrl: "https://github.com/owner/repo",
      status: "pending",
      userId: testUser.id,
    };
    mockDb.returning.mockReturnValueOnce([mockSubmission]);

    const app = createApp(testUser);
    const res = await app.request("/api/submissions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ gitUrl: "https://github.com/owner/repo" }),
    });
    expect(res.status).toBe(201);
    const body = await res.json();
    expect(body.id).toBe("sub-1");
    expect(body.status).toBe("pending");
  });
});

describe("GET /api/submissions", () => {
  test("returns 401 if not authenticated", async () => {
    const app = createApp(null);
    const res = await app.request("/api/submissions");
    expect(res.status).toBe(401);
  });

  test("returns only own submissions for regular user", async () => {
    const mockSubs = [{ id: "sub-1", userId: testUser.id, status: "pending", gitUrl: "https://github.com/a/b" }];
    mockDb.where.mockReturnValueOnce(mockSubs);

    const app = createApp(testUser);
    const res = await app.request("/api/submissions");
    expect(res.status).toBe(200);
  });

  test("returns all submissions for curator", async () => {
    const mockSubs = [
      { id: "sub-1", userId: "user-1", status: "pending" },
      { id: "sub-2", userId: "user-2", status: "approved" },
    ];
    mockDb.where.mockReturnValueOnce(mockSubs);

    const app = createApp(testCurator);
    const res = await app.request("/api/submissions");
    expect(res.status).toBe(200);
  });
});
```

### Step 2: Run test to verify it fails

Run: `cd forge && bun test tests/routes/submissions.test.ts`
Expected: FAIL — `../../src/routes/submissions` does not exist

### Step 3: Add submissions table to schema

Modify `forge/src/db/schema.ts` — add after the `comments` table:

```ts
export const submissions = pgTable("submissions", {
  id: uuid("id").defaultRandom().primaryKey(),
  pluginId: uuid("plugin_id").references(() => plugins.id),
  userId: uuid("user_id").notNull().references(() => users.id),
  gitUrl: text("git_url").notNull(),
  description: text("description"),
  status: text("status").notNull().default("pending"), // pending | approved | rejected
  reviewerId: uuid("reviewer_id").references(() => users.id),
  reviewNote: text("review_note"),
  createdAt: timestamp("created_at").defaultNow().notNull(),
  reviewedAt: timestamp("reviewed_at"),
});
```

### Step 4: Create the submissions route

Create `forge/src/routes/submissions.ts`:

```ts
import { Hono } from "hono";
import { db } from "../db";
import { submissions } from "../db/schema";
import { eq, and } from "drizzle-orm";

const app = new Hono();

// POST /api/submissions — create a submission
app.post("/", async (c) => {
  const user = c.get("user");
  if (!user) return c.json({ error: "Unauthorized" }, 401);

  const body = await c.req.json().catch(() => null);
  if (!body || !body.gitUrl) {
    return c.json({ error: "gitUrl is required" }, 400);
  }

  const gitUrl = String(body.gitUrl).trim();
  const gitUrlPattern = /^https:\/\/(github\.com|gitlab\.com)\/[\w.-]+\/[\w.-]+(\.git)?$/;
  if (!gitUrlPattern.test(gitUrl)) {
    return c.json({ error: "Invalid git URL. Must be a GitHub or GitLab repository URL." }, 400);
  }

  const [submission] = await db
    .insert(submissions)
    .values({
      userId: user.id,
      gitUrl,
      description: body.description || null,
      status: "pending",
    })
    .returning();

  return c.json({ id: submission.id, status: submission.status, gitUrl: submission.gitUrl }, 201);
});

// GET /api/submissions — list submissions
app.get("/", async (c) => {
  const user = c.get("user");
  if (!user) return c.json({ error: "Unauthorized" }, 401);

  const isCuratorOrAdmin = user.role === "curator" || user.role === "admin";

  let results;
  if (isCuratorOrAdmin) {
    results = await db.select().from(submissions);
  } else {
    results = await db.select().from(submissions).where(eq(submissions.userId, user.id));
  }

  return c.json(results);
});

export default app;
```

### Step 5: Register the route in the app

Modify `forge/src/index.ts` (or wherever routes are registered) — add:

```ts
import submissionsRoutes from "./routes/submissions";
app.route("/api/submissions", submissionsRoutes);
```

Check the existing route registration pattern first and match it.

### Step 6: Run tests to verify they pass (green)

Run: `cd forge && bun test tests/routes/submissions.test.ts`
Expected: All tests PASS

### Step 7: Run full test suite

Run: `cd forge && bun test`
Expected: All existing tests still pass

### Step 8: Commit

```bash
git add forge/src/db/schema.ts forge/src/routes/submissions.ts forge/tests/routes/submissions.test.ts
git commit -m "feat(forge): add submissions table and POST/GET endpoints"
```

---

## Task 2: Submission review endpoint

**Owner:** forge-dev
**Files:**
- Modify: `forge/src/routes/submissions.ts`
- Modify: `forge/tests/routes/submissions.test.ts`

### Step 1: Write failing tests for review endpoint (red)

Add to `forge/tests/routes/submissions.test.ts`:

```ts
describe("POST /api/submissions/:id/review", () => {
  test("returns 401 if not authenticated", async () => {
    const app = createApp(null);
    const res = await app.request("/api/submissions/sub-1/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(401);
  });

  test("returns 403 if not curator or admin", async () => {
    const app = createApp(testUser);
    const res = await app.request("/api/submissions/sub-1/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(403);
  });

  test("returns 400 if action is invalid", async () => {
    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-1/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "maybe" }),
    });
    expect(res.status).toBe(400);
  });

  test("returns 404 if submission not found", async () => {
    mockDb.where.mockReturnValueOnce([]);
    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/nonexistent/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(404);
  });

  test("approves a pending submission", async () => {
    const mockSub = { id: "sub-1", status: "pending", pluginId: "plugin-1" };
    mockDb.where.mockReturnValueOnce([mockSub]); // find submission
    mockDb.returning.mockReturnValueOnce([{ ...mockSub, status: "approved" }]); // update submission
    mockDb.returning.mockReturnValueOnce([{ id: "plugin-1", status: "approved" }]); // update plugin

    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-1/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("approved");
  });

  test("rejects a pending submission with note", async () => {
    const mockSub = { id: "sub-1", status: "pending", pluginId: "plugin-1" };
    mockDb.where.mockReturnValueOnce([mockSub]);
    mockDb.returning.mockReturnValueOnce([{ ...mockSub, status: "rejected" }]);
    mockDb.returning.mockReturnValueOnce([{ id: "plugin-1", status: "rejected" }]);

    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-1/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "reject", note: "Missing README" }),
    });
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("rejected");
  });

  test("returns 409 if submission already reviewed", async () => {
    const mockSub = { id: "sub-1", status: "approved", pluginId: "plugin-1" };
    mockDb.where.mockReturnValueOnce([mockSub]);

    const app = createApp(testCurator);
    const res = await app.request("/api/submissions/sub-1/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "approve" }),
    });
    expect(res.status).toBe(409);
  });
});
```

### Step 2: Run test to verify it fails

Run: `cd forge && bun test tests/routes/submissions.test.ts`
Expected: FAIL — route not found (404 for POST /:id/review)

### Step 3: Implement the review endpoint

Add to `forge/src/routes/submissions.ts`:

```ts
import { plugins } from "../db/schema";

// POST /api/submissions/:id/review — curator approves or rejects
app.post("/:id/review", async (c) => {
  const user = c.get("user");
  if (!user) return c.json({ error: "Unauthorized" }, 401);
  if (user.role !== "curator" && user.role !== "admin") {
    return c.json({ error: "Forbidden" }, 403);
  }

  const body = await c.req.json().catch(() => null);
  if (!body || !["approve", "reject"].includes(body.action)) {
    return c.json({ error: "action must be 'approve' or 'reject'" }, 400);
  }

  const submissionId = c.req.param("id");
  const [submission] = await db
    .select()
    .from(submissions)
    .where(eq(submissions.id, submissionId));

  if (!submission) return c.json({ error: "Submission not found" }, 404);
  if (submission.status !== "pending") {
    return c.json({ error: "Submission already reviewed" }, 409);
  }

  const newStatus = body.action === "approve" ? "approved" : "rejected";

  const [updated] = await db
    .update(submissions)
    .set({
      status: newStatus,
      reviewerId: user.id,
      reviewNote: body.note || null,
      reviewedAt: new Date(),
    })
    .where(eq(submissions.id, submissionId))
    .returning();

  // Update plugin status if linked
  if (submission.pluginId) {
    await db
      .update(plugins)
      .set({ status: newStatus })
      .where(eq(plugins.id, submission.pluginId));
  }

  return c.json({ id: updated.id, status: updated.status });
});
```

### Step 4: Run tests (green)

Run: `cd forge && bun test tests/routes/submissions.test.ts`
Expected: All tests PASS

### Step 5: Run full test suite

Run: `cd forge && bun test`
Expected: All tests pass

### Step 6: Commit

```bash
git add forge/src/routes/submissions.ts forge/tests/routes/submissions.test.ts
git commit -m "feat(forge): add curator review endpoint for submissions"
```

---

## Task 3: Submit page (Forge UI)

**Owner:** forge-dev
**Files:**
- Create: `forge/src/views/submit.ts`
- Modify: `forge/src/routes/pages.ts` — add `/submit` route
- Modify: `forge/src/views/layout.ts` — add "Submit" link in nav (if authenticated)
- Create: `forge/tests/routes/submit-page.test.ts`

### Step 1: Write failing test (red)

Create `forge/tests/routes/submit-page.test.ts`:

```ts
import { describe, test, expect, mock, beforeEach } from "bun:test";

mock.module("../../src/db", () => ({
  db: { insert: mock(), select: mock() },
}));
mock.module("../../src/lib/supabase", () => ({
  supabase: { auth: { getUser: mock() } },
}));

import { Hono } from "hono";
import pages from "../../src/routes/pages";

const testUser = { id: "user-1", email: "test@example.com", role: "user", displayName: "Test", authId: "auth-1" };

function createApp(user: typeof testUser | null = null) {
  const app = new Hono();
  app.use("*", async (c, next) => {
    c.set("user", user);
    await next();
  });
  app.route("/", pages);
  return app;
}

describe("GET /submit", () => {
  test("redirects to login if not authenticated", async () => {
    const app = createApp(null);
    const res = await app.request("/submit");
    expect(res.status).toBe(302);
  });

  test("renders submit form if authenticated", async () => {
    const app = createApp(testUser);
    const res = await app.request("/submit");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("Submit a Plugin");
    expect(html).toContain('name="gitUrl"');
  });
});
```

### Step 2: Run test to verify it fails

Run: `cd forge && bun test tests/routes/submit-page.test.ts`
Expected: FAIL — 404 for GET /submit

### Step 3: Create submit view

Create `forge/src/views/submit.ts`:

```ts
export function submitPage(): string {
  return `
    <div class="max-w-2xl mx-auto">
      <h1 class="text-2xl font-bold mb-6">Submit a Plugin</h1>
      <p class="text-gray-600 mb-6">Submit a GitHub or GitLab repository containing a Claude Code plugin for review by our curators.</p>

      <form hx-post="/api/submissions" hx-target="#submit-result" hx-swap="innerHTML" class="space-y-4">
        <div>
          <label for="gitUrl" class="block text-sm font-medium text-gray-700 mb-1">Repository URL *</label>
          <input type="url" name="gitUrl" id="gitUrl" required
            placeholder="https://github.com/owner/repo"
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500" />
          <p class="mt-1 text-sm text-gray-500">Must be a public GitHub or GitLab repository.</p>
        </div>

        <div>
          <label for="description" class="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
          <textarea name="description" id="description" rows="3"
            placeholder="Brief description of what this plugin does..."
            class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-indigo-500 focus:border-indigo-500"></textarea>
        </div>

        <button type="submit"
          class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
          Submit for Review
        </button>
      </form>

      <div id="submit-result" class="mt-4"></div>
    </div>
  `;
}

export function submitSuccess(submissionId: string): string {
  return `
    <div class="rounded-md bg-green-50 p-4">
      <p class="text-sm font-medium text-green-800">
        Submission received! Your plugin is pending review by our curators.
      </p>
      <p class="mt-1 text-sm text-green-700">
        <a href="/my/submissions" class="underline">Track your submissions</a>
      </p>
    </div>
  `;
}
```

### Step 4: Add /submit route to pages

Add to `forge/src/routes/pages.ts`:

```ts
import { submitPage } from "../views/submit";

// GET /submit — submission form (authenticated)
app.get("/submit", (c) => {
  const user = c.get("user");
  if (!user) return c.redirect("/auth/login");
  return c.html(layout("Submit a Plugin", submitPage(), { user }));
});
```

### Step 5: Update HTMX response in submissions route

The `POST /api/submissions` endpoint needs to return HTML when called via HTMX. Modify `forge/src/routes/submissions.ts` — in the POST handler, after creating the submission:

```ts
// If HTMX request, return HTML partial
if (c.req.header("HX-Request")) {
  const { submitSuccess } = await import("../views/submit");
  return c.html(submitSuccess(submission.id));
}

return c.json({ id: submission.id, status: submission.status, gitUrl: submission.gitUrl }, 201);
```

### Step 6: Run tests (green)

Run: `cd forge && bun test tests/routes/submit-page.test.ts`
Expected: All PASS

### Step 7: Run full test suite

Run: `cd forge && bun test`

### Step 8: Commit

```bash
git add forge/src/views/submit.ts forge/src/routes/pages.ts forge/tests/routes/submit-page.test.ts
git commit -m "feat(forge): add /submit page with form for plugin submissions"
```

---

## Task 4: Inline curator review on plugin detail page

**Owner:** forge-dev
**Files:**
- Create: `forge/src/views/components/submission-review.ts`
- Modify: `forge/src/routes/pages.ts` — plugin detail page shows review banner for curators
- Modify: `forge/tests/routes/pages.test.ts` — add tests for curator view of pending plugin

### Step 1: Write failing test (red)

Add to `forge/tests/routes/pages.test.ts` (or create a dedicated test file):

```ts
describe("GET /plugins/:name (curator viewing pending plugin)", () => {
  test("shows review banner for curator when plugin is pending", async () => {
    // Mock plugin with status "pending" and linked submission
    // Mock user as curator
    // Assert response contains "pending review" banner and approve/reject buttons
  });

  test("does not show review banner for regular user", async () => {
    // Mock plugin with status "pending"
    // Mock user as regular user
    // Assert 404 (regular users shouldn't see pending plugins)
  });

  test("does not show review banner for approved plugin", async () => {
    // Mock plugin with status "approved"
    // Mock user as curator
    // Assert no review banner present
  });
});
```

Flesh out with actual mock patterns matching existing `pages.test.ts`.

### Step 2: Run to verify failure, then implement

Create `forge/src/views/components/submission-review.ts`:

```ts
export function submissionReviewBanner(submission: { id: string; userId: string; gitUrl: string; description: string | null }): string {
  return `
    <div class="rounded-md bg-yellow-50 border border-yellow-200 p-4 mb-6">
      <h3 class="text-sm font-medium text-yellow-800">This plugin is pending review</h3>
      <p class="mt-1 text-sm text-yellow-700">Submitted from: ${submission.gitUrl}</p>
      ${submission.description ? `<p class="mt-1 text-sm text-yellow-700">${submission.description}</p>` : ""}

      <div class="mt-4 flex gap-3">
        <button
          hx-post="/api/submissions/${submission.id}/review"
          hx-vals='{"action":"approve"}'
          hx-target="#review-result"
          hx-swap="innerHTML"
          class="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700">
          Approve
        </button>

        <div x-data="{ showReject: false }">
          <button @click="showReject = !showReject"
            class="inline-flex items-center px-3 py-1.5 border border-transparent text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700">
            Reject
          </button>
          <div x-show="showReject" class="mt-2">
            <input type="text" id="reject-note" placeholder="Reason for rejection..."
              class="w-full px-3 py-1.5 border border-gray-300 rounded-md text-sm" />
            <button
              hx-post="/api/submissions/${submission.id}/review"
              hx-vals='js:{"action":"reject","note":document.getElementById("reject-note").value}'
              hx-target="#review-result"
              hx-swap="innerHTML"
              class="mt-1 inline-flex items-center px-3 py-1.5 text-sm font-medium rounded-md text-white bg-red-600 hover:bg-red-700">
              Confirm Reject
            </button>
          </div>
        </div>
      </div>

      <div id="review-result" class="mt-2"></div>
    </div>
  `;
}
```

### Step 3: Modify plugin detail page

In `forge/src/routes/pages.ts`, in the `/plugins/:name` handler:
- If user is curator/admin and plugin status is "pending", query the submissions table for the linked submission
- Pass it to the view to render the review banner above the plugin detail
- If user is regular and plugin status is not "approved", return 404

### Step 4: Add HTMX response to review endpoint

In `forge/src/routes/submissions.ts`, the POST `/:id/review` handler should return HTML for HTMX:

```ts
if (c.req.header("HX-Request")) {
  const message = newStatus === "approved"
    ? '<div class="text-green-700 font-medium">Plugin approved and now visible in catalogue.</div>'
    : '<div class="text-red-700 font-medium">Plugin rejected.</div>';
  return c.html(message);
}
```

### Step 5: Run tests (green)

Run: `cd forge && bun test`
Expected: All pass

### Step 6: Commit

```bash
git add forge/src/views/components/submission-review.ts forge/src/routes/pages.ts forge/tests/routes/pages.test.ts
git commit -m "feat(forge): add inline curator review on plugin detail page"
```

**Steel thread complete at this point.** A user can submit a URL → curator views the pending plugin → approves/rejects → approved plugin appears in catalogue.

---

## Task 5: Async indexing on submission

**Owner:** forge-dev
**Files:**
- Modify: `forge/src/routes/submissions.ts`
- Modify: `forge/tests/routes/submissions.test.ts`
- May need to modify: `forge/src/lib/indexer.ts` (to support indexing a submission rather than a registry)

### Step 1: Write failing tests (red)

Tests for:
- Submission with valid plugin repo → creates plugin record with `pending` status, links pluginId
- Submission with invalid repo (no plugin.json) → submission auto-rejected with reason
- Submission with duplicate gitUrl (already submitted) → returns 409

### Step 2: Implement

In `POST /api/submissions`, after creating the submission record:
1. Create a registry entry (or reuse existing) for the git URL
2. Call the indexer to extract plugin metadata
3. If indexing succeeds: create plugin with `status: 'pending'`, link `pluginId` to submission
4. If indexing fails: update submission to `status: 'rejected'` with `reviewNote` explaining the failure

Key: reuse `indexRegistry()` from `forge/src/lib/indexer.ts`. May need a variant that creates plugins with `pending` status instead of `approved`.

### Step 3: Run tests (green), full suite, commit

```bash
git commit -m "feat(forge): auto-index plugin on submission and validate structure"
```

---

## Task 6: CLI auth commands (`openforge auth login/logout/status`)

**Owner:** cli-dev
**Files:**
- Create: `cli/src/openforge/auth.py`
- Create: `cli/src/openforge/api_client.py`
- Modify: `cli/src/openforge/cli.py` — register `auth` sub-Typer
- Create: `cli/tests/test_auth.py`

### Step 1: Write failing tests (red)

```python
# tests/test_auth.py
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
import typer

runner = CliRunner()

def test_login_prompts_for_credentials():
    """Verify login command prompts for email and password."""
    from openforge.auth import auth_app
    app = typer.Typer()
    app.add_typer(auth_app, name="auth")
    result = runner.invoke(app, ["auth", "login"], input="test@example.com\npassword123\n")
    assert result.exit_code == 0 or "error" not in result.output.lower()

def test_login_stores_token():
    """Verify successful login stores token to config dir."""
    # Mock Supabase auth response
    # Verify token file written to ~/.config/openforge/token.json

def test_logout_clears_token():
    """Verify logout removes stored token."""

def test_status_shows_authenticated_user():
    """Verify status shows email when logged in."""

def test_status_shows_not_authenticated():
    """Verify status shows not logged in when no token."""
```

### Step 2: Implement auth module

`cli/src/openforge/auth.py`:
- `auth_app = typer.Typer()` (sub-Typer for `openforge auth`)
- `login` command: prompt email+password, POST to Forge's Supabase Auth endpoint, store tokens in `~/.config/openforge/token.json`
- `logout` command: delete token file
- `status` command: read token, validate, show user info
- Helper: `get_auth_token()` — read stored token, refresh if expired

`cli/src/openforge/api_client.py`:
- `ForgeClient` class wrapping `httpx.Client`
- Reads Forge URL from config
- Adds auth token header
- Methods: `submit(git_url, description)`, `get_submissions()`

### Step 3: Register in cli.py

```python
from openforge.auth import auth_app
app.add_typer(auth_app, name="auth")
```

### Step 4: Run tests (green), full suite, commit

```bash
git commit -m "feat(cli): add auth login/logout/status commands with token storage"
```

---

## Task 7: CLI `openforge publish` command

**Owner:** cli-dev
**Files:**
- Create: `cli/src/openforge/publish.py`
- Modify: `cli/src/openforge/cli.py` — register publish command
- Create: `cli/tests/test_publish.py`

### Step 1: Write failing tests (red)

```python
# tests/test_publish.py
def test_publish_requires_auth():
    """Verify publish fails with helpful message if not logged in."""

def test_publish_validates_git_url():
    """Verify publish rejects invalid URLs."""

def test_publish_sends_submission_to_forge():
    """Verify publish POSTs to /api/submissions and shows result."""

def test_publish_with_description():
    """Verify --description flag is sent to API."""

def test_publish_handles_server_error():
    """Verify graceful error handling on API failure."""

def test_publish_handles_network_error():
    """Verify graceful handling of connection refused."""

def test_publish_handles_duplicate_submission():
    """Verify 409 from server shows helpful message."""
```

### Step 2: Implement

`cli/src/openforge/publish.py`:

```python
def publish_command(
    git_url: str = typer.Argument(..., help="GitHub or GitLab repository URL"),
    description: str | None = typer.Option(None, "--description", "-d", help="Brief description"),
) -> None:
    """Submit a plugin to The Forge for review."""
    from openforge.api_client import ForgeClient
    from openforge.auth import get_auth_token

    token = get_auth_token()
    if not token:
        console.print("[red]Not logged in. Run 'openforge auth login' first.[/red]")
        raise typer.Exit(code=1)

    client = ForgeClient(token=token)
    result = client.submit(git_url, description)
    console.print(f"[green]Submission created![/green] Status: {result['status']}")
    console.print(f"Track at: {client.forge_url}/my/submissions")
```

Register in `cli.py`:
```python
from openforge.publish import publish_command
app.command("publish")(publish_command)
```

### Step 3: Run tests (green), full suite, commit

```bash
git commit -m "feat(cli): add publish command for submitting plugins to Forge"
```

---

## Task 8: Submitter status page (`/my/submissions`)

**Owner:** forge-dev
**Files:**
- Create: `forge/src/views/my-submissions.ts`
- Modify: `forge/src/routes/pages.ts` — add `/my/submissions` route
- Create: `forge/tests/routes/my-submissions.test.ts`

### Step 1: Write failing tests (red)

- Unauthenticated → redirect to login
- Authenticated with no submissions → shows empty state
- Authenticated with submissions → shows table with status, date, links
- Rejected submission → shows rejection reason

### Step 2: Implement view and route

Table view showing: plugin name (or git URL if not yet indexed), status badge (pending=yellow, approved=green, rejected=red), submitted date, rejection note if applicable.

### Step 3: Run tests (green), commit

```bash
git commit -m "feat(forge): add /my/submissions page for tracking submission status"
```

---

## Task 9: Curator dashboard (`/curator/submissions`)

**Owner:** forge-dev
**Files:**
- Create: `forge/src/views/curator-dashboard.ts`
- Modify: `forge/src/routes/pages.ts` — add `/curator/submissions` route
- Modify: `forge/src/views/layout.ts` — add pending count badge in nav for curators
- Create: `forge/tests/routes/curator-dashboard.test.ts`

### Step 1: Write failing tests (red)

- Unauthenticated → redirect
- Regular user → 403
- Curator → sees all submissions table
- Filter by status (query param `?status=pending`)
- Pending count badge in nav

### Step 2: Implement

- Dashboard table: plugin name, submitter email, submitted date, status, "Review" link
- Filter tabs: All | Pending | Approved | Rejected
- Sort by date (newest first)
- Click "Review" → goes to `/plugins/:name` (where inline review lives)
- Nav badge: query pending count, show in layout

### Step 3: Run tests (green), commit

```bash
git commit -m "feat(forge): add curator dashboard with submission filters and nav badge"
```

---

## Task 10: Notifications (email on approve/reject)

**Owner:** forge-dev
**Files:**
- Create: `forge/src/lib/notifications.ts`
- Modify: `forge/src/routes/submissions.ts` — send notification after review
- Create: `forge/tests/lib/notifications.test.ts`

### Step 1: Write failing tests (red)

- Approve triggers notification to submitter
- Reject triggers notification with reason
- Notification failure doesn't block the review response

### Step 2: Implement

Use Supabase's built-in email (or a simple SMTP call). Fire-and-forget — notification failure should log but not block the review.

### Step 3: Run tests (green), full suite, commit

```bash
git commit -m "feat(forge): add email notifications for submission review decisions"
```

---

## Task 11: Catalogue and API filter updates

**Owner:** forge-dev
**Files:**
- Modify: `forge/src/routes/api.ts` — ensure marketplace.json and skills index only return approved
- Modify: `forge/src/routes/pages.ts` — catalogue only shows approved
- Modify: `forge/tests/routes/api.test.ts`
- Modify: `forge/tests/routes/pages.test.ts`

### Step 1: Write failing tests (red)

- `GET /api/marketplace.json` does not include pending or rejected plugins
- `GET /.well-known/skills/index.json` does not include pending or rejected
- Catalogue page does not show pending or rejected plugins to regular users
- Catalogue shows pending plugins to curators (with visual indicator)

### Step 2: Verify and harden existing filters

The existing queries already filter `status="approved"` — verify this, add explicit tests, and ensure no leakage.

### Step 3: Run tests (green), commit

```bash
git commit -m "fix(forge): harden catalogue and API to exclude non-approved plugins"
```

---

## Summary

| Task | Owner | Description | Dependencies |
|------|-------|-------------|-------------|
| 1 | forge-dev | Submissions table + POST/GET API | — |
| 2 | forge-dev | Review endpoint (approve/reject) | 1 |
| 3 | forge-dev | /submit page (Forge UI) | 1 |
| 4 | forge-dev | Inline curator review on detail page | 2 |
| 5 | forge-dev | Async indexing on submission | 1 |
| 6 | cli-dev | Auth commands (login/logout/status) | — |
| 7 | cli-dev | `openforge publish` command | 6, 1 |
| 8 | forge-dev | /my/submissions page | 1 |
| 9 | forge-dev | Curator dashboard | 2 |
| 10 | forge-dev | Email notifications | 2 |
| 11 | forge-dev | Harden catalogue/API filters | 1 |

**Parallelism:** Tasks 1-4 (steel thread, sequential). Task 6 (CLI auth) can start in parallel with tasks 1-4. Tasks 5, 7-11 widen after the steel thread.
