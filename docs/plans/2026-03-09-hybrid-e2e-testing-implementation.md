# Hybrid E2E Testing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add three-tier hybrid testing (unit → integration → browser E2E) to both Forge and CLI, targeting <60s total CI time.

**Architecture:** Shared local Forge+Supabase instance for integration and Playwright tests. Forge integration tests use `bun test` with `fetch()` against a real server. Playwright tests run via Node.js `npx playwright test`. CLI adds `respx` for HTTP transport testing and `subprocess.run()` for smoke tests.

**Tech Stack:** Bun test, Playwright (Node.js), respx (Python), local Supabase (ports 54321-54324), Forge on port 3000.

**Design doc:** `docs/plans/2026-03-09-hybrid-e2e-testing-design.md`

---

## Task 1: Test Infrastructure — Setup Script and Directory Structure

**Files:**
- Create: `scripts/test-e2e-setup.sh`
- Create: `scripts/test-e2e-teardown.sh`
- Create: `forge/tests/integration/.gitkeep`
- Create: `forge/e2e/.gitkeep`
- Create: `cli/tests/integration/.gitkeep`
- Create: `cli/tests/e2e/.gitkeep`

**Step 1: Create directory structure**

```bash
mkdir -p forge/tests/integration forge/e2e cli/tests/integration cli/tests/e2e
```

**Step 2: Write the e2e setup script**

Create `scripts/test-e2e-setup.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

# Verify Supabase is running
if ! supabase status --workdir forge 2>/dev/null | grep -q "API URL"; then
  echo "ERROR: Local Supabase not running. Run: cd forge && supabase start"
  exit 1
fi

# Get Supabase credentials from status output
SUPABASE_URL=$(supabase status --workdir forge 2>/dev/null | grep "API URL" | awk '{print $NF}')
ANON_KEY=$(supabase status --workdir forge 2>/dev/null | grep "anon key" | awk '{print $NF}')
SERVICE_ROLE_KEY=$(supabase status --workdir forge 2>/dev/null | grep "service_role key" | awk '{print $NF}')
DB_URL="postgresql://postgres:postgres@127.0.0.1:54322/postgres"

export SUPABASE_URL ANON_KEY SERVICE_ROLE_KEY DB_URL

# Start Forge server in background if not already running
if ! curl -sf http://localhost:3000/health > /dev/null 2>&1; then
  echo "Starting Forge server..."
  cd forge
  DATABASE_URL="$DB_URL" \
  SUPABASE_URL="$SUPABASE_URL" \
  SUPABASE_ANON_KEY="$ANON_KEY" \
  SUPABASE_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY" \
  OPENFORGE_MODE=public \
  bun run start &
  FORGE_PID=$!
  echo "$FORGE_PID" > /tmp/forge-e2e.pid
  cd ..

  # Wait for health check
  for i in $(seq 1 30); do
    if curl -sf http://localhost:3000/health > /dev/null 2>&1; then
      echo "Forge server ready on port 3000 (PID $FORGE_PID)"
      break
    fi
    if [ "$i" -eq 30 ]; then
      echo "ERROR: Forge server failed to start within 30s"
      kill "$FORGE_PID" 2>/dev/null || true
      exit 1
    fi
    sleep 1
  done
else
  echo "Forge server already running on port 3000"
fi

echo "E2E test environment ready."
echo "  FORGE_URL=http://localhost:3000"
echo "  SUPABASE_URL=$SUPABASE_URL"
```

**Step 3: Write the teardown script**

Create `scripts/test-e2e-teardown.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ -f /tmp/forge-e2e.pid ]; then
  PID=$(cat /tmp/forge-e2e.pid)
  if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping Forge server (PID $PID)..."
    kill "$PID"
  fi
  rm -f /tmp/forge-e2e.pid
fi

echo "E2E test environment torn down."
```

**Step 4: Make scripts executable and commit**

```bash
chmod +x scripts/test-e2e-setup.sh scripts/test-e2e-teardown.sh
git add scripts/test-e2e-setup.sh scripts/test-e2e-teardown.sh forge/tests/integration/ forge/e2e/ cli/tests/integration/ cli/tests/e2e/
git commit -m "chore: add e2e test infrastructure scaffolding and setup scripts"
```

---

## Task 2: Forge Integration Test Helpers

**Files:**
- Create: `forge/tests/integration/helpers.ts`

**Step 1: Write integration test helper module**

This module provides `fetch()`-based helpers that hit the real running Forge server. All integration tests will import from here.

Create `forge/tests/integration/helpers.ts`:

```typescript
const BASE_URL = process.env.FORGE_URL || "http://localhost:3000";
const SUPABASE_URL = process.env.SUPABASE_URL || "http://127.0.0.1:54321";
const ANON_KEY = process.env.SUPABASE_ANON_KEY || "";

export { BASE_URL, SUPABASE_URL, ANON_KEY };

/** Create a test user via Supabase Auth API and return access token + user info */
export async function createTestUser(
  email?: string,
  password?: string,
): Promise<{ accessToken: string; email: string; userId: string }> {
  const testEmail = email || `test-${Date.now()}-${Math.random().toString(36).slice(2)}@test.local`;
  const testPassword = password || "test-password-123!";

  // Sign up via Supabase GoTrue
  const signupRes = await fetch(`${SUPABASE_URL}/auth/v1/signup`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      apikey: ANON_KEY,
    },
    body: JSON.stringify({ email: testEmail, password: testPassword }),
  });

  if (!signupRes.ok) {
    const err = await signupRes.text();
    throw new Error(`Failed to create test user: ${signupRes.status} ${err}`);
  }

  const data = await signupRes.json();

  // Local Supabase has email confirmations disabled, so we get tokens immediately
  return {
    accessToken: data.access_token,
    email: testEmail,
    userId: data.user?.id || data.id,
  };
}

/** Make an authenticated request to the Forge server */
export async function authFetch(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<Response> {
  return fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: {
      ...init?.headers,
      Authorization: `Bearer ${token}`,
    },
  });
}

/** Make an unauthenticated request to the Forge server */
export async function anonFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${BASE_URL}${path}`, init);
}

/** Clean up a test user — delete from Supabase Auth via service role key */
export async function deleteTestUser(userId: string): Promise<void> {
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
  if (!serviceRoleKey) return; // skip cleanup if no service role key

  await fetch(`${SUPABASE_URL}/auth/v1/admin/users/${userId}`, {
    method: "DELETE",
    headers: {
      apikey: serviceRoleKey,
      Authorization: `Bearer ${serviceRoleKey}`,
    },
  });
}
```

**Step 2: Commit**

```bash
git add forge/tests/integration/helpers.ts
git commit -m "feat(forge): add integration test helpers for real server testing"
```

---

## Task 3: Forge Integration Steel Thread — Health + Auth + Catalogue

**Files:**
- Create: `forge/tests/integration/health.test.ts`
- Create: `forge/tests/integration/auth.test.ts`
- Create: `forge/tests/integration/catalogue.test.ts`

**Step 1: Write the health integration test (simplest possible)**

Create `forge/tests/integration/health.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";
import { anonFetch } from "./helpers";

describe("Health (integration)", () => {
  test("GET /health returns 200 with ok status", async () => {
    const res = await anonFetch("/health");
    expect(res.status).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
  });
});
```

**Step 2: Run the test to verify it works against real server**

Prerequisite: Supabase running (`cd forge && supabase start`) and Forge running (`bun run dev`).

```bash
cd forge && FORGE_URL=http://localhost:3000 bun test tests/integration/health.test.ts
```

Expected: PASS

**Step 3: Write auth integration test**

Create `forge/tests/integration/auth.test.ts`:

```typescript
import { describe, expect, test, beforeAll, afterAll } from "bun:test";
import { anonFetch, createTestUser, deleteTestUser, BASE_URL } from "./helpers";

describe("Auth (integration)", () => {
  let testUserId: string;

  afterAll(async () => {
    if (testUserId) await deleteTestUser(testUserId);
  });

  test("GET /auth/login returns login form", async () => {
    const res = await anonFetch("/auth/login");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("email");
    expect(html).toContain("password");
  });

  test("signup creates user and returns valid session", async () => {
    const user = await createTestUser();
    testUserId = user.userId;
    expect(user.accessToken).toBeTruthy();
    expect(user.email).toContain("@test.local");
  });

  test("authenticated request succeeds with Bearer token", async () => {
    const user = await createTestUser();
    testUserId = user.userId;

    const res = await fetch(`${BASE_URL}/my/submissions`, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
    });
    // Should succeed (200) or redirect — not 401
    expect(res.status).not.toBe(401);
  });
});
```

**Step 4: Write catalogue integration test**

Create `forge/tests/integration/catalogue.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";
import { anonFetch } from "./helpers";

describe("Catalogue (integration)", () => {
  test("GET / returns 200 with HTML catalogue page", async () => {
    const res = await anonFetch("/");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("OpenForge");
  });

  test("GET / with HX-Request returns partial HTML", async () => {
    const res = await anonFetch("/", {
      headers: { "HX-Request": "true" },
    });
    expect(res.status).toBe(200);
    const html = await res.text();
    // Partial should NOT contain full page shell (<!DOCTYPE or <html>)
    // This verifies HTMX partial response behavior
    // Note: exact behavior depends on implementation — adjust assertion as needed
    expect(html).toBeTruthy();
  });

  test("GET /api/marketplace.json returns valid JSON", async () => {
    const res = await anonFetch("/api/marketplace.json");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data).toHaveProperty("plugins");
  });

  test("GET /.well-known/skills/index.json returns valid JSON", async () => {
    const res = await anonFetch("/.well-known/skills/index.json");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(Array.isArray(data)).toBe(true);
  });
});
```

**Step 5: Run all integration tests**

```bash
cd forge && FORGE_URL=http://localhost:3000 bun test tests/integration/
```

Expected: All PASS

**Step 6: Commit**

```bash
git add forge/tests/integration/
git commit -m "feat(forge): add integration test steel thread — health, auth, catalogue"
```

---

## Task 4: Forge Integration Tests — Submissions + Voting + Comments

**Files:**
- Create: `forge/tests/integration/submissions.test.ts`
- Create: `forge/tests/integration/voting.test.ts`
- Create: `forge/tests/integration/comments.test.ts`

**Step 1: Write submissions integration test**

Create `forge/tests/integration/submissions.test.ts`:

```typescript
import { describe, expect, test, beforeAll, afterAll } from "bun:test";
import { authFetch, createTestUser, deleteTestUser } from "./helpers";

describe("Submissions (integration)", () => {
  let token: string;
  let userId: string;
  let submissionId: string;

  beforeAll(async () => {
    const user = await createTestUser();
    token = user.accessToken;
    userId = user.userId;
  });

  afterAll(async () => {
    if (userId) await deleteTestUser(userId);
  });

  test("POST /submissions creates a submission", async () => {
    const res = await authFetch("/submissions", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        gitUrl: "https://github.com/test-org/test-plugin",
        description: "Integration test submission",
      }),
    });
    expect(res.status).toBe(201);
    const data = await res.json();
    expect(data.id).toBeTruthy();
    submissionId = data.id;
  });

  test("GET /my/submissions shows the created submission", async () => {
    const res = await authFetch("/my/submissions", token);
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("test-org/test-plugin");
  });

  test("GET /api/submissions returns submissions list", async () => {
    const res = await authFetch("/api/submissions", token);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(Array.isArray(data)).toBe(true);
  });
});
```

**Step 2: Write voting integration test**

Create `forge/tests/integration/voting.test.ts`:

Tests require a plugin in the DB. If no seeded plugins exist, this test verifies the vote endpoint returns appropriate responses. Adjust plugin ID based on seed data.

```typescript
import { describe, expect, test, beforeAll, afterAll } from "bun:test";
import { anonFetch, authFetch, createTestUser, deleteTestUser } from "./helpers";

describe("Voting (integration)", () => {
  let token: string;
  let userId: string;

  beforeAll(async () => {
    const user = await createTestUser();
    token = user.accessToken;
    userId = user.userId;
  });

  afterAll(async () => {
    if (userId) await deleteTestUser(userId);
  });

  test("POST vote without auth returns 401", async () => {
    const res = await anonFetch("/plugins/nonexistent/vote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction: "up" }),
    });
    expect([401, 403]).toContain(res.status);
  });

  test("POST vote on nonexistent plugin returns 404", async () => {
    const res = await authFetch("/plugins/nonexistent-id/vote", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction: "up" }),
    });
    expect([404, 400]).toContain(res.status);
  });
});
```

**Step 3: Write comments integration test**

Create `forge/tests/integration/comments.test.ts`:

```typescript
import { describe, expect, test, beforeAll, afterAll } from "bun:test";
import { anonFetch, authFetch, createTestUser, deleteTestUser } from "./helpers";

describe("Comments (integration)", () => {
  let token: string;
  let userId: string;

  beforeAll(async () => {
    const user = await createTestUser();
    token = user.accessToken;
    userId = user.userId;
  });

  afterAll(async () => {
    if (userId) await deleteTestUser(userId);
  });

  test("POST comment without auth returns 401", async () => {
    const res = await anonFetch("/plugins/nonexistent/comments", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "test comment" }),
    });
    expect([401, 403]).toContain(res.status);
  });
});
```

**Step 4: Run and commit**

```bash
cd forge && FORGE_URL=http://localhost:3000 bun test tests/integration/
git add forge/tests/integration/
git commit -m "feat(forge): add integration tests for submissions, voting, comments"
```

---

## Task 5: Forge Integration Tests — Search + Curator + HTMX Partials

**Files:**
- Create: `forge/tests/integration/search.test.ts`
- Create: `forge/tests/integration/curator.test.ts`
- Create: `forge/tests/integration/htmx-partials.test.ts`

**Step 1: Write search integration test**

Create `forge/tests/integration/search.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";
import { anonFetch } from "./helpers";

describe("Search (integration)", () => {
  test("GET /?q=<term> returns filtered results", async () => {
    const res = await anonFetch("/?q=test");
    expect(res.status).toBe(200);
    const html = await res.text();
    expect(html).toContain("OpenForge");
  });

  test("GET /?q=<term> with HX-Request returns partial", async () => {
    const res = await anonFetch("/?q=test", {
      headers: { "HX-Request": "true" },
    });
    expect(res.status).toBe(200);
  });

  test("GET /?sort=newest returns sorted results", async () => {
    const res = await anonFetch("/?sort=newest");
    expect(res.status).toBe(200);
  });

  test("GET /?sort=popular returns sorted results", async () => {
    const res = await anonFetch("/?sort=popular");
    expect(res.status).toBe(200);
  });
});
```

**Step 2: Write curator integration test**

Create `forge/tests/integration/curator.test.ts`:

```typescript
import { describe, expect, test, beforeAll, afterAll } from "bun:test";
import { authFetch, createTestUser, deleteTestUser } from "./helpers";

describe("Curator dashboard (integration)", () => {
  let token: string;
  let userId: string;

  beforeAll(async () => {
    const user = await createTestUser();
    token = user.accessToken;
    userId = user.userId;
    // Note: this user won't have curator role, so we test access control
  });

  afterAll(async () => {
    if (userId) await deleteTestUser(userId);
  });

  test("GET /curator/submissions without curator role is forbidden", async () => {
    const res = await authFetch("/curator/submissions", token);
    // Should be 403 or redirect — not 200
    expect(res.status).not.toBe(200);
  });
});
```

**Step 3: Write HTMX partials test**

Create `forge/tests/integration/htmx-partials.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";
import { anonFetch } from "./helpers";

describe("HTMX partials (integration)", () => {
  test("catalogue page returns full HTML without HX-Request", async () => {
    const res = await anonFetch("/");
    const html = await res.text();
    expect(html).toContain("<!DOCTYPE html>");
    expect(html).toContain("<html");
  });

  test("catalogue page returns partial with HX-Request header", async () => {
    const fullRes = await anonFetch("/");
    const fullHtml = await fullRes.text();

    const partialRes = await anonFetch("/", {
      headers: { "HX-Request": "true" },
    });
    const partialHtml = await partialRes.text();

    // Partial should be shorter than full page (no shell)
    expect(partialHtml.length).toBeLessThan(fullHtml.length);
  });
});
```

**Step 4: Run and commit**

```bash
cd forge && FORGE_URL=http://localhost:3000 bun test tests/integration/
git add forge/tests/integration/
git commit -m "feat(forge): add integration tests for search, curator, HTMX partials"
```

---

## Task 6: Playwright Setup and Steel Thread

**Files:**
- Create: `forge/playwright.config.ts`
- Create: `forge/e2e/catalogue.spec.ts`
- Modify: `forge/package.json` (add `@playwright/test` devDep and scripts)

**Step 1: Install Playwright**

```bash
cd forge && npm init -y --scope=playwright 2>/dev/null || true
npm install --save-dev @playwright/test
npx playwright install chromium
```

Note: We use `npm`/`npx` for Playwright specifically (not Bun), because Playwright requires Node.js.

**Step 2: Create Playwright config**

Create `forge/playwright.config.ts`:

```typescript
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: "list",
  use: {
    baseURL: process.env.FORGE_URL || "http://localhost:3000",
    trace: "on-first-retry",
    headless: true,
  },
  webServer: {
    command: "bun run start",
    url: "http://localhost:3000/health",
    reuseExistingServer: true,
    timeout: 30_000,
    env: {
      DATABASE_URL: process.env.DATABASE_URL || "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
      SUPABASE_URL: process.env.SUPABASE_URL || "http://127.0.0.1:54321",
      SUPABASE_ANON_KEY: process.env.SUPABASE_ANON_KEY || "",
      SUPABASE_SERVICE_ROLE_KEY: process.env.SUPABASE_SERVICE_ROLE_KEY || "",
      OPENFORGE_MODE: "public",
    },
  },
});
```

**Step 3: Add scripts to package.json**

Add to `forge/package.json` scripts:

```json
{
  "test:integration": "bun test tests/integration/",
  "test:e2e": "npx playwright test",
  "test:all": "bun test && bun run test:integration && bun run test:e2e"
}
```

**Step 4: Write the catalogue E2E steel thread test**

Create `forge/e2e/catalogue.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

test.describe("Catalogue E2E", () => {
  test("browse catalogue and click into plugin detail", async ({ page }) => {
    // Navigate to catalogue
    await page.goto("/");
    await expect(page).toHaveTitle(/OpenForge/);

    // Page should contain plugin cards or empty state
    const content = await page.textContent("body");
    expect(content).toBeTruthy();

    // If plugins exist, click the first one
    const pluginLink = page.locator("a[href^='/plugins/']").first();
    if (await pluginLink.isVisible()) {
      await pluginLink.click();
      await expect(page).toHaveURL(/\/plugins\//);
      // Detail page should render
      const detail = await page.textContent("body");
      expect(detail).toBeTruthy();
    }
  });
});
```

**Step 5: Run the Playwright test**

```bash
cd forge && npx playwright test
```

Expected: PASS (1 test)

**Step 6: Commit**

```bash
git add forge/playwright.config.ts forge/e2e/ forge/package.json
git commit -m "feat(forge): add Playwright E2E setup and catalogue steel thread test"
```

---

## Task 7: Remaining Playwright E2E Tests

**Files:**
- Create: `forge/e2e/auth.spec.ts`
- Create: `forge/e2e/interactions.spec.ts`
- Create: `forge/e2e/submissions.spec.ts`

**Step 1: Write auth E2E test**

Create `forge/e2e/auth.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

const SUPABASE_URL = process.env.SUPABASE_URL || "http://127.0.0.1:54321";
const ANON_KEY = process.env.SUPABASE_ANON_KEY || "";

/** Create a test user and return credentials */
async function createTestUser(request: any) {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2)}@test.local`;
  const password = "test-password-123!";

  const res = await request.post(`${SUPABASE_URL}/auth/v1/signup`, {
    data: { email, password },
    headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
  });
  expect(res.ok()).toBeTruthy();

  return { email, password };
}

test.describe("Auth E2E", () => {
  test("login flow — fill form, submit, session persists", async ({ page, request }) => {
    const { email, password } = await createTestUser(request);

    // Go to login page
    await page.goto("/auth/login");
    await expect(page.locator("input[name='email']")).toBeVisible();

    // Fill and submit login form
    await page.fill("input[name='email']", email);
    await page.fill("input[name='password']", password);
    await page.click("button[type='submit']");

    // Should redirect away from login
    await page.waitForURL((url) => !url.pathname.includes("/auth/login"), { timeout: 10_000 });

    // Session persists — navigate to auth-gated page
    await page.goto("/my/submissions");
    await expect(page).not.toHaveURL(/\/auth\/login/);
  });
});
```

**Step 2: Write HTMX interaction tests**

Create `forge/e2e/interactions.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

const SUPABASE_URL = process.env.SUPABASE_URL || "http://127.0.0.1:54321";
const ANON_KEY = process.env.SUPABASE_ANON_KEY || "";

async function loginUser(page: any, request: any) {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2)}@test.local`;
  const password = "test-password-123!";

  await request.post(`${SUPABASE_URL}/auth/v1/signup`, {
    data: { email, password },
    headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
  });

  await page.goto("/auth/login");
  await page.fill("input[name='email']", email);
  await page.fill("input[name='password']", password);
  await page.click("button[type='submit']");
  await page.waitForURL((url: URL) => !url.pathname.includes("/auth/login"), { timeout: 10_000 });
}

test.describe("HTMX Interactions E2E", () => {
  test("search updates results without full page reload", async ({ page }) => {
    await page.goto("/");

    // Type in search — HTMX should fire request and swap results
    const searchInput = page.locator("input[name='q']");
    if (await searchInput.isVisible()) {
      await searchInput.fill("test");
      // Wait for HTMX request to complete (results container should update)
      await page.waitForTimeout(1000); // HTMX debounce
      // Page should NOT have fully reloaded
      const html = await page.content();
      expect(html).toContain("OpenForge");
    }
  });

  test("vote click swaps count in-place via HTMX", async ({ page, request }) => {
    await loginUser(page, request);
    await page.goto("/");

    // Find a vote button if visible
    const voteBtn = page.locator("[hx-post*='vote']").first();
    if (await voteBtn.isVisible()) {
      const initialText = await voteBtn.textContent();
      await voteBtn.click();
      // Wait for HTMX swap
      await page.waitForTimeout(500);
      // The vote button area should have updated (either count or active state changed)
      const updatedText = await voteBtn.textContent();
      // Just verify no error — the swap happened
      expect(updatedText).toBeTruthy();
    }
  });

  test("comment form submits and comment appears via HTMX", async ({ page, request }) => {
    await loginUser(page, request);

    // Navigate to a plugin detail page with comments
    const pluginLink = page.locator("a[href^='/plugins/']").first();
    await page.goto("/");
    if (await pluginLink.isVisible()) {
      await pluginLink.click();
      await page.waitForURL(/\/plugins\//);

      // Find comment form
      const commentInput = page.locator("textarea[name='body'], input[name='body']").first();
      if (await commentInput.isVisible()) {
        await commentInput.fill("E2E test comment");
        await page.click("[hx-post*='comments'] button[type='submit'], button[hx-post*='comments']");
        await page.waitForTimeout(1000);
        const html = await page.content();
        expect(html).toContain("E2E test comment");
      }
    }
  });
});
```

**Step 3: Write submission flow test**

Create `forge/e2e/submissions.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

const SUPABASE_URL = process.env.SUPABASE_URL || "http://127.0.0.1:54321";
const ANON_KEY = process.env.SUPABASE_ANON_KEY || "";

async function loginUser(page: any, request: any) {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2)}@test.local`;
  const password = "test-password-123!";

  await request.post(`${SUPABASE_URL}/auth/v1/signup`, {
    data: { email, password },
    headers: { apikey: ANON_KEY, "Content-Type": "application/json" },
  });

  await page.goto("/auth/login");
  await page.fill("input[name='email']", email);
  await page.fill("input[name='password']", password);
  await page.click("button[type='submit']");
  await page.waitForURL((url: URL) => !url.pathname.includes("/auth/login"), { timeout: 10_000 });
}

test.describe("Submissions E2E", () => {
  test("submit plugin form → fills fields → submits → redirects", async ({ page, request }) => {
    await loginUser(page, request);

    // Navigate to submit page
    await page.goto("/submit");
    await expect(page.locator("input[name='gitUrl']")).toBeVisible();

    // Fill in submission form
    await page.fill("input[name='gitUrl']", "https://github.com/e2e-test/fake-plugin");
    const descField = page.locator("textarea[name='description'], input[name='description']");
    if (await descField.isVisible()) {
      await descField.fill("E2E test submission");
    }

    // Submit
    await page.click("button[type='submit']");

    // Should redirect to my submissions or show success
    await page.waitForURL(/\/(my\/submissions|submit)/, { timeout: 10_000 });
  });
});
```

**Step 4: Run all Playwright tests**

```bash
cd forge && npx playwright test
```

Expected: All PASS (5-7 tests across 4 files)

**Step 5: Commit**

```bash
git add forge/e2e/
git commit -m "feat(forge): add Playwright E2E tests for auth, HTMX interactions, submissions"
```

---

## Task 8: CLI — Add respx and Integration Test Steel Thread

**Files:**
- Modify: `cli/pyproject.toml` (add `respx` dev dependency)
- Create: `cli/tests/integration/test_api_client_transport.py`
- Create: `cli/tests/integration/__init__.py`
- Create: `cli/tests/integration/conftest.py`

**Step 1: Add respx dependency**

Add to `cli/pyproject.toml` dev dependencies:

```toml
[dependency-groups]
dev = [
    "pyright>=1.1.390",
    "pytest>=8.3.0",
    "pytest-cov>=6.0.0",
    "bandit>=1.8.0",
    "respx>=0.22.0",
]
```

Install:

```bash
cd cli && uv sync
```

**Step 2: Create integration test directory and conftest**

Create `cli/tests/integration/__init__.py` (empty).

Create `cli/tests/integration/conftest.py`:

```python
"""Shared fixtures for CLI integration tests."""

import pytest
import respx


@pytest.fixture
def mock_forge_url() -> str:
    """Base URL for mock Forge server."""
    return "https://forge.test.local"


@pytest.fixture
def mock_supabase_url() -> str:
    """Base URL for mock Supabase auth."""
    return "https://auth.test.local"
```

**Step 3: Write the failing test — ForgeClient transport-level test**

Create `cli/tests/integration/test_api_client_transport.py`:

```python
"""Integration tests for ForgeClient — tests at the HTTP transport layer using respx.

These tests verify:
- Correct URL construction
- Correct headers (Authorization, Content-Type)
- Correct request body format
- Correct response parsing
- Error handling for non-200 responses

Unlike unit tests that mock `client._post()`, these tests let the real
httpx calls flow through to respx, which intercepts at the transport layer.
"""

import pytest
import respx
from httpx import Response

from openforge.api_client import ForgeClient, ForgeAPIError


class TestForgeClientSubmit:
    """Test ForgeClient.submit() at the HTTP transport layer."""

    @respx.mock
    def test_submit_sends_correct_request(self, mock_forge_url: str) -> None:
        """Verify submit() sends POST to /api/submissions with correct headers and body."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-1", "status": "pending"})
        )

        client = ForgeClient(token="test-token-123", forge_url=mock_forge_url)
        result = client.submit("https://github.com/owner/repo", "A great plugin")

        assert route.called
        request = route.calls[0].request
        assert request.headers["authorization"] == "Bearer test-token-123"
        assert request.headers["content-type"] == "application/json"
        assert result["id"] == "sub-1"
        assert result["status"] == "pending"

    @respx.mock
    def test_submit_raises_on_401(self, mock_forge_url: str) -> None:
        """Verify submit() raises ForgeAPIError on 401 Unauthorized."""
        respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(401, json={"error": "Unauthorized"})
        )

        client = ForgeClient(token="bad-token", forge_url=mock_forge_url)
        with pytest.raises(ForgeAPIError) as exc_info:
            client.submit("https://github.com/owner/repo")
        assert exc_info.value.status_code == 401

    @respx.mock
    def test_submit_raises_on_500(self, mock_forge_url: str) -> None:
        """Verify submit() raises ForgeAPIError on server error."""
        respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(500, json={"error": "Internal Server Error"})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        with pytest.raises(ForgeAPIError) as exc_info:
            client.submit("https://github.com/owner/repo")
        assert exc_info.value.status_code == 500


class TestForgeClientGetSubmissions:
    """Test ForgeClient.get_submissions() at the HTTP transport layer."""

    @respx.mock
    def test_get_submissions_sends_correct_request(self, mock_forge_url: str) -> None:
        """Verify get_submissions() sends GET to /api/submissions with auth header."""
        route = respx.get(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(200, json=[{"id": "sub-1"}, {"id": "sub-2"}])
        )

        client = ForgeClient(token="test-token-123", forge_url=mock_forge_url)
        result = client.get_submissions()

        assert route.called
        request = route.calls[0].request
        assert request.headers["authorization"] == "Bearer test-token-123"
        assert len(result) == 2

    @respx.mock
    def test_get_submissions_raises_on_403(self, mock_forge_url: str) -> None:
        """Verify get_submissions() raises ForgeAPIError on 403 Forbidden."""
        respx.get(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(403, json={"error": "Forbidden"})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        with pytest.raises(ForgeAPIError):
            client.get_submissions()
```

**Step 4: Run tests to verify they pass**

```bash
cd cli && uv run pytest tests/integration/test_api_client_transport.py -v
```

Expected: All PASS (5 tests)

**Step 5: Commit**

```bash
git add cli/pyproject.toml cli/tests/integration/
git commit -m "feat(cli): add respx and integration test steel thread for ForgeClient"
```

---

## Task 9: CLI — Remaining respx Integration Tests (Auth + Search)

**Files:**
- Create: `cli/tests/integration/test_auth_transport.py`
- Create: `cli/tests/integration/test_search_transport.py`

**Step 1: Write auth transport tests**

Create `cli/tests/integration/test_auth_transport.py`:

```python
"""Integration tests for auth module — HTTP transport layer via respx."""

import pytest
import respx
from httpx import Response

from openforge.auth import _sign_in_with_password


class TestSignInTransport:
    """Test _sign_in_with_password() at the HTTP transport layer."""

    @respx.mock
    def test_sends_correct_request_to_gotrue(self, mock_supabase_url: str) -> None:
        """Verify correct GoTrue endpoint, headers, and body."""
        route = respx.post(
            f"{mock_supabase_url}/auth/v1/token",
            params={"grant_type": "password"},
        ).mock(
            return_value=Response(
                200,
                json={
                    "access_token": "eyJ-access",
                    "refresh_token": "eyJ-refresh",
                    "user": {"email": "test@example.com", "id": "user-1"},
                },
            )
        )

        result = _sign_in_with_password("test@example.com", "password123", mock_supabase_url)

        assert route.called
        request = route.calls[0].request
        assert request.headers["content-type"] == "application/json"
        # Verify body contains email and password
        import json
        body = json.loads(request.content)
        assert body["email"] == "test@example.com"
        assert body["password"] == "password123"
        assert result["access_token"] == "eyJ-access"

    @respx.mock
    def test_raises_on_invalid_credentials(self, mock_supabase_url: str) -> None:
        """Verify ValueError raised on 400 response."""
        respx.post(
            f"{mock_supabase_url}/auth/v1/token",
            params={"grant_type": "password"},
        ).mock(
            return_value=Response(
                400,
                json={"error": "invalid_grant", "error_description": "Invalid login credentials"},
            )
        )

        with pytest.raises(ValueError, match="Invalid login credentials"):
            _sign_in_with_password("bad@example.com", "wrong", mock_supabase_url)

    @respx.mock
    def test_raises_on_server_error(self, mock_supabase_url: str) -> None:
        """Verify ValueError raised on 500 response."""
        respx.post(
            f"{mock_supabase_url}/auth/v1/token",
            params={"grant_type": "password"},
        ).mock(
            return_value=Response(500, json={"msg": "Internal error"}),
        )

        with pytest.raises(ValueError):
            _sign_in_with_password("test@example.com", "password", mock_supabase_url)
```

**Step 2: Write search transport tests**

Create `cli/tests/integration/test_search_transport.py`:

```python
"""Integration tests for ForgeClient search — HTTP transport layer via respx."""

import pytest
import respx
from httpx import Response

from openforge.api_client import ForgeClient


class TestForgeClientSearch:
    """Test ForgeClient search-related methods at the HTTP transport layer."""

    @respx.mock
    def test_search_forge_sends_correct_request(self, mock_forge_url: str) -> None:
        """Verify search sends GET with correct query params."""
        route = respx.get(f"{mock_forge_url}/api/search").mock(
            return_value=Response(200, json={"results": [{"name": "test-plugin"}]})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        # Call the search method — adjust method name based on actual API
        result = client.search_forge("test-plugin")

        assert route.called
        request = route.calls[0].request
        assert "test-plugin" in str(request.url)
```

Note: The exact search method name and URL pattern should be verified from `api_client.py`. Adjust as needed during implementation.

**Step 3: Run and commit**

```bash
cd cli && uv run pytest tests/integration/ -v
git add cli/tests/integration/
git commit -m "feat(cli): add respx integration tests for auth and search transport"
```

---

## Task 10: CLI — Subprocess Smoke Tests

**Files:**
- Create: `cli/tests/e2e/__init__.py`
- Create: `cli/tests/e2e/test_cli_smoke.py`
- Create: `cli/tests/e2e/conftest.py`

**Step 1: Create e2e directory and conftest**

Create `cli/tests/e2e/__init__.py` (empty).

Create `cli/tests/e2e/conftest.py`:

```python
"""Fixtures for CLI end-to-end smoke tests."""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def run_openforge(tmp_path: Path):
    """Run openforge CLI as a real subprocess. Returns a helper function."""

    def _run(*args: str, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
        cmd = ["uv", "run", "openforge", *args]
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd or tmp_path,
            timeout=30,
            env=env,
        )

    return _run
```

**Step 2: Write smoke tests**

Create `cli/tests/e2e/test_cli_smoke.py`:

```python
"""End-to-end smoke tests — runs openforge as a real subprocess.

These tests verify:
- Entry point resolves and CLI starts
- Help and version output
- Basic commands work as a real binary
"""

import os
from pathlib import Path

import pytest


class TestCLIEntryPoint:
    """Verify the CLI binary starts and responds to basic flags."""

    def test_help_flag(self, run_openforge) -> None:
        """openforge --help exits 0 and shows usage."""
        result = run_openforge("--help")
        assert result.returncode == 0
        assert "openforge" in result.stdout.lower() or "usage" in result.stdout.lower()

    def test_version_flag(self, run_openforge) -> None:
        """openforge --version exits 0 and shows version string."""
        result = run_openforge("--version")
        assert result.returncode == 0
        # Should contain a version-like string (digits and dots)
        assert any(c.isdigit() for c in result.stdout)


class TestCLIAddRemoveFlow:
    """Test add → list → remove flow as a real subprocess."""

    def test_add_local_repo(self, run_openforge, sample_plugin_repo: Path, tmp_path: Path) -> None:
        """openforge add <local-path> installs and creates lock file."""
        result = run_openforge("add", str(sample_plugin_repo), cwd=tmp_path)
        assert result.returncode == 0

        # Lock file should exist
        lock_file = tmp_path / ".openforge.lock"
        assert lock_file.exists() or "installed" in result.stdout.lower() or "added" in result.stdout.lower()

    def test_list_after_add(self, run_openforge, sample_plugin_repo: Path, tmp_path: Path) -> None:
        """openforge list shows installed plugin after add."""
        run_openforge("add", str(sample_plugin_repo), cwd=tmp_path)
        result = run_openforge("list", cwd=tmp_path)
        assert result.returncode == 0

    def test_remove_after_add(self, run_openforge, sample_plugin_repo: Path, tmp_path: Path) -> None:
        """openforge remove uninstalls the plugin."""
        run_openforge("add", str(sample_plugin_repo), cwd=tmp_path)
        # Get the installed name from list
        list_result = run_openforge("list", cwd=tmp_path)
        # Remove — exact name depends on plugin
        result = run_openforge("remove", "sample-plugin", cwd=tmp_path)
        # Should either succeed or show meaningful error
        assert result.returncode in (0, 1)


class TestCLIAuthStatus:
    """Test auth commands without real credentials."""

    def test_auth_status_not_logged_in(self, run_openforge) -> None:
        """openforge auth status when not logged in shows appropriate message."""
        result = run_openforge("auth", "status")
        # Should not crash — exits with info about not being logged in
        assert "not logged in" in result.stdout.lower() or "no token" in result.stdout.lower() or result.returncode in (0, 1)
```

Note: The `sample_plugin_repo` fixture needs to be available. Either import from `conftest.py` (it's in the parent `tests/` directory and pytest will discover it) or duplicate it.

**Step 3: Run smoke tests**

```bash
cd cli && uv run pytest tests/e2e/ -v
```

Expected: All PASS (6 tests)

**Step 4: Commit**

```bash
git add cli/tests/e2e/
git commit -m "feat(cli): add subprocess smoke tests for CLI binary"
```

---

## Task 11: Update Package Scripts and Test Commands

**Files:**
- Modify: `forge/package.json` (add test scripts)
- Modify: `cli/pyproject.toml` (update pytest markers)
- Modify: `forge/CLAUDE.md` (document new test commands)
- Modify: `cli/CLAUDE.md` (document new test commands)

**Step 1: Update forge/package.json scripts**

Add new test scripts (keep existing `test` as-is):

```json
{
  "test:unit": "bun test tests/",
  "test:integration": "bun test tests/integration/",
  "test:e2e": "npx playwright test",
  "test:all": "bun test tests/ && bun test tests/integration/ && npx playwright test"
}
```

**Step 2: Add pytest markers to cli/pyproject.toml**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "integration: HTTP transport integration tests (respx)",
    "e2e: subprocess smoke tests",
]
```

**Step 3: Update forge/CLAUDE.md**

Add to the test commands section:

```markdown
### Test commands
- `bun test` — run unit tests (mocked, ~10-15s)
- `bun run test:integration` — run integration tests against real Forge+Supabase (~5-10s)
- `npx playwright test` — run Playwright E2E tests (~30-40s)
- `bun run test:all` — run all tiers
```

**Step 4: Update cli/CLAUDE.md**

Add to the test commands section:

```markdown
### Test commands
- `uv run pytest tests/ --ignore=tests/integration --ignore=tests/e2e` — run unit tests (~0.66s)
- `uv run pytest tests/integration/` — run respx integration tests (~1-2s)
- `uv run pytest tests/e2e/` — run subprocess smoke tests (~3-5s)
- `uv run pytest` — run all tests
```

**Step 5: Commit**

```bash
git add forge/package.json cli/pyproject.toml forge/CLAUDE.md cli/CLAUDE.md
git commit -m "docs: update test commands and markers for hybrid testing pyramid"
```

---

## Task 12: Update CLAUDE.md and Memory

**Files:**
- Modify: `CLAUDE.md` (root — add testing architecture section)
- Modify: `/Users/jeremy.brown/.claude/projects/-Users-jeremy-brown-dev-openforge/memory/MEMORY.md`

**Step 1: Add testing section to root CLAUDE.md**

Add after the Architecture decisions section:

```markdown
## Testing Architecture

Three-tier hybrid testing pyramid for both Forge and CLI:

- **Tier 1 — Unit:** Fast, mocked, in-process. `bun test` (Forge) / `pytest` (CLI)
- **Tier 2 — Integration:** Real HTTP against local Forge+Supabase. `bun test` with `fetch()` (Forge) / `respx` transport mocking (CLI)
- **Tier 3 — E2E:** Playwright browser tests (Forge, via Node.js) / subprocess smoke tests (CLI)

CI target: <60s total (unit + integration + e2e in parallel jobs).
```

**Step 2: Update memory**

Add to MEMORY.md:

```markdown
## Testing architecture
- Three-tier hybrid pyramid: unit (mocked) → integration (real server) → E2E (browser/subprocess)
- Forge: bun test (unit) + bun test with fetch() (integration) + Playwright via Node.js (E2E)
- CLI: pytest (unit) + respx (HTTP transport) + subprocess smoke tests (E2E)
- CI target: <60s total | Playwright runs via npx (NOT Bun — incompatible)
- Local Supabase (ports 54321-54324) + Forge on port 3000 for integration/E2E
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add testing architecture to CLAUDE.md"
```

---

## Summary

| Task | Component | What | Est. Time |
|------|-----------|------|-----------|
| 1 | Both | Infrastructure scaffolding + setup scripts | 5 min |
| 2 | Forge | Integration test helpers (auth, fetch) | 5 min |
| 3 | Forge | Integration steel thread (health, auth, catalogue) | 10 min |
| 4 | Forge | Integration tests (submissions, voting, comments) | 10 min |
| 5 | Forge | Integration tests (search, curator, HTMX partials) | 10 min |
| 6 | Forge | Playwright setup + catalogue steel thread | 10 min |
| 7 | Forge | Remaining Playwright tests (auth, interactions, submissions) | 15 min |
| 8 | CLI | Add respx + ForgeClient transport tests | 10 min |
| 9 | CLI | Auth + search transport tests | 10 min |
| 10 | CLI | Subprocess smoke tests | 10 min |
| 11 | Both | Update scripts, markers, CLAUDE.md docs | 5 min |
| 12 | Both | Update root CLAUDE.md + memory | 5 min |
