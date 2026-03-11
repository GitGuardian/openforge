# Cross-Component E2E Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a cross-component E2E test harness and two happy-path scenarios verifying the full CLI↔Forge user journey: publish via CLI → curator approves in browser → plugin appears in catalogue.

**Architecture:** Playwright is the test runner. CLI is invoked via `child_process.spawnSync('uv', ['run', 'openforge', ...args], { cwd: CLI_DIR, env })` — args array only, no shell string interpolation. Tests live in `forge/e2e/cross-component.spec.ts`. The `promoteUserToCurator` helper was added in the Forge plan (Task 4) — this plan depends on it existing in `forge/e2e/helpers.ts`.

**Verification scope:** The cross-component tests verify CLI publish → Forge curator UI → marketplace.json reflects approval. A full filesystem install via `openforge add forge:<name>` is NOT included (requires the indexer to complete background cloning, which is non-deterministic in tests) — that is covered by CLI integration tests separately.

**Tech Stack:** Playwright (`@playwright/test`), Node.js `child_process.spawnSync`, local Supabase (port 54321), local Forge (port 3000), Python CLI (`uv run openforge`)

**Prerequisites:**
- Forge plan (2026-03-11-forge-test-gaps-plan.md) Task 4 complete — `promoteUserToCurator` and `createTestSubmission` must exist in `forge/e2e/helpers.ts`
- CLI plan (2026-03-11-cli-test-gaps-plan.md) Task 5 complete — `XDG_CONFIG_HOME` token isolation verified working
- Local Supabase running, local Forge server running
- `uv sync` completed in `cli/`
- All commands run from `forge/`

---

## Chunk 1: Harness + Scenarios

### Task 1: Build the CLI spawn helper

**Files:**
- Create: `forge/e2e/cli-helper.ts`

- [ ] **Step 1: Verify prerequisite — promoteUserToCurator exists in helpers.ts**

```bash
grep -n "promoteUserToCurator\|createTestSubmission\|SERVICE_ROLE_KEY" forge/e2e/helpers.ts
```

Expected: all three should be present. If not, complete the Forge plan Task 4 first.

- [ ] **Step 2: Verify XDG_CONFIG_HOME isolation works for the CLI**

```bash
XDG_CONFIG_HOME=/tmp/xdg-test uv --project cli run python -c \
  "from platformdirs import user_config_dir; print(user_config_dir('openforge'))"
```

Expected: `/tmp/xdg-test/openforge`. If different, note the correct platform env var.

- [ ] **Step 3: Write the CLI helper**

```typescript
/**
 * CLI spawn helper for cross-component E2E tests.
 *
 * Uses spawnSync with an explicit args array — never shell string interpolation.
 * CLI working directory is cli/ so uv can resolve pyproject.toml.
 * Token isolation: XDG_CONFIG_HOME is set per-test to a temp dir.
 */

import { spawnSync } from "child_process";
import { resolve } from "path";

/** Absolute path to the cli/ directory (one level up from forge/, one more up from e2e/) */
export const CLI_DIR = resolve(__dirname, "../../cli");

export interface CLIResult {
  exitCode: number;
  stdout: string;
  stderr: string;
}

/**
 * Run an openforge CLI command as a subprocess.
 *
 * @param args - CLI subcommands + arguments, e.g. ['auth', 'login'] or ['publish', 'https://...']
 * @param env  - Additional env vars merged into the subprocess environment
 * @param input - Optional stdin string (for interactive prompts)
 */
export function runCLI(
  args: string[],
  env: Record<string, string> = {},
  input?: string,
): CLIResult {
  const result = spawnSync("uv", ["run", "openforge", ...args], {
    cwd: CLI_DIR,
    env: {
      ...process.env,
      OPENFORGE_FORGE_URL: "http://localhost:3000",
      OPENFORGE_SUPABASE_URL:
        process.env.SUPABASE_URL || "http://127.0.0.1:54321",
      ...env,
    },
    input,
    encoding: "utf-8",
    timeout: 30_000,
  });

  return {
    exitCode: result.status ?? 1,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
  };
}

/**
 * Log in via the CLI non-interactively by piping email + password to stdin.
 * Token is stored in XDG_CONFIG_HOME/openforge/token.json.
 */
export function cliLogin(
  email: string,
  password: string,
  xdgConfigHome: string,
): CLIResult {
  return runCLI(
    ["auth", "login"],
    { XDG_CONFIG_HOME: xdgConfigHome },
    `${email}\n${password}\n`,
  );
}

/**
 * Submit a plugin via the CLI.
 * Requires prior login (token in xdgConfigHome/openforge/token.json).
 */
export function cliPublish(
  gitUrl: string,
  description: string,
  xdgConfigHome: string,
): CLIResult {
  return runCLI(
    ["publish", gitUrl, "--description", description],
    { XDG_CONFIG_HOME: xdgConfigHome },
  );
}
```

- [ ] **Step 4: Verify the helper file has no TypeScript errors**

Note: `forge/tsconfig.json` covers `src/` and `tests/` but not `e2e/`. The Playwright runner uses its own TypeScript compilation — type errors are caught at test runtime, not by `bun run typecheck`. If you want to check types manually:

```bash
npx tsc --noEmit --strict forge/e2e/cli-helper.ts 2>&1 | head -20
```

Ignore errors about missing tsconfig — the Playwright runner handles compilation. Fix any genuine type errors (e.g. `spawnSync` return type issues).

- [ ] **Step 5: Commit**

```bash
git add forge/e2e/cli-helper.ts
git commit -m "test(forge): add CLI spawn helper for cross-component E2E tests"
```

---

### Task 2: Cross-component E2E scenarios

**Files:**
- Create: `forge/e2e/cross-component.spec.ts`

- [ ] **Step 1: Verify the SUPABASE_SERVICE_ROLE_KEY is available**

```bash
grep "SERVICE_ROLE_KEY\|service_role" forge/.env | head -3
supabase status 2>/dev/null | grep service_role
```

Note the key — it must be in `forge/.env` so `helpers.ts` can load it via `dotenv`.

- [ ] **Step 2: Understand the curator approval flow from curator.spec.ts**

```bash
cat forge/e2e/curator.spec.ts | head -60
```

Reuse the same `signIn` helper pattern.

- [ ] **Step 3: Write the failing test file**

```typescript
import { mkdtempSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { test, expect } from "@playwright/test";
import {
  createE2EUser,
  loginViaUI,
  promoteUserToCurator,
  SUPABASE_URL,
  ANON_KEY,
} from "./helpers";
import { cliLogin, cliPublish } from "./cli-helper";

/** Sign in and return userId + token */
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

test.describe("Cross-Component E2E", () => {
  let tmpXdg: string;

  test.beforeEach(() => {
    // Isolated XDG_CONFIG_HOME per test — CLI writes token.json here
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
    // 1. Create and promote a curator user
    const { email, password } = await createE2EUser(request);
    const { userId } = await signIn(request, email, password);
    await promoteUserToCurator(request, userId);

    // 2. Login via CLI (writes token to tmpXdg/openforge/token.json)
    const loginResult = cliLogin(email, password, tmpXdg);
    expect(loginResult.exitCode).toBe(0);

    // 3. Publish a plugin via CLI
    const gitUrl = `https://github.com/tenfourty/cc-marketplace`;
    const publishResult = cliPublish(gitUrl, "Cross-component E2E test", tmpXdg);
    expect(publishResult.exitCode).toBe(0);

    // 4. Curator reviews in browser
    await loginViaUI(page, email, password);
    await page.goto("/curator/submissions");
    await expect(page).toHaveURL(/\/curator\/submissions/);
    await expect(page.locator("body")).not.toContainText("403");

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

    // 5. Verify the dashboard didn't error after approval
    await expect(page).toHaveURL(/\/curator\/submissions/);
    await expect(page.locator("body")).not.toContainText("Internal Server Error");
  });

  test("CLI publish → curator approves via API → plugin appears in catalogue", async ({
    page,
    request,
  }) => {
    // 1. Create and promote a curator user
    const { email, password } = await createE2EUser(request);
    const { userId, token } = await signIn(request, email, password);
    await promoteUserToCurator(request, userId);

    // 2. CLI login + publish
    const loginResult = cliLogin(email, password, tmpXdg);
    expect(loginResult.exitCode).toBe(0);

    const gitUrl = `https://github.com/tenfourty/cc-marketplace`;
    const publishResult = cliPublish(gitUrl, "Cross-component catalogue test", tmpXdg);
    expect(publishResult.exitCode).toBe(0);

    // 3. Approve via curator browser (same pattern as Scenario 1)
    await loginViaUI(page, email, password);
    await page.goto("/curator/submissions");
    await expect(page).toHaveURL(/\/curator\/submissions/);
    await expect(page.locator("body")).not.toContainText("403");

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

    // 4. Check marketplace.json — approved plugin's gitUrl must appear
    const marketplaceRes = await request.get("http://localhost:3000/api/marketplace.json");
    expect(marketplaceRes.ok()).toBe(true);
    const marketplace = await marketplaceRes.json();
    const packages: string[] = (marketplace.packages ?? []).map(
      (p: { git_url?: string; url?: string }) => p.git_url ?? p.url ?? "",
    );
    expect(packages).toContain(gitUrl);
  });
});
```

- [ ] **Step 4: Run to verify failing (red)**

```bash
npx playwright test e2e/cross-component.spec.ts --reporter=list
```

Expected: FAIL. Likely failures:
- `cliLogin` exits non-zero: `XDG_CONFIG_HOME` isolation not working → check CLI plan Task 5
- `cliPublish` exits non-zero: submission fails → check Forge server is running and auth token path is correct
- `promoteUserToCurator` fails → check `SUPABASE_SERVICE_ROLE_KEY` is loaded

Run each step manually to diagnose:
```bash
# Test CLI login manually
TMPDIR=$(mktemp -d)
XDG_CONFIG_HOME=$TMPDIR OPENFORGE_SUPABASE_URL=http://127.0.0.1:54321 \
  uv --project cli run openforge auth login
# Enter email/password when prompted
ls $TMPDIR/openforge/  # Should show token.json
```

If CLI login works manually but fails in the test, the issue is stdin handling — update `cliLogin` input format.

- [ ] **Step 5: Investigate and fix issues systematically**

For each failing assertion, add `console.log` to print CLI stdout/stderr before asserting:
```typescript
console.log('login stdout:', loginResult.stdout);
console.log('login stderr:', loginResult.stderr);
```

Fix issues found. Notify team-lead if any cross-component bugs are discovered (e.g., CLI doesn't read token from XDG path, or Forge rejects CLI submissions).

- [ ] **Step 6: Run to confirm passing (green)**

```bash
npx playwright test e2e/cross-component.spec.ts --reporter=list
```

Expected: both tests pass. These are slower (20-40s each) due to CLI subprocess + Supabase calls.

- [ ] **Step 7: Run full E2E suite**

```bash
npx playwright test --reporter=list
```

Expected: all tests pass (20+ component tests + 2 cross-component = 22+).

- [ ] **Step 8: Commit**

```bash
git add forge/e2e/cross-component.spec.ts
git commit -m "test(forge): add cross-component E2E tests — CLI publish to curator approval"
```

---

## Final Verification

- [ ] **Run full test suites (Forge + CLI)**

From `forge/`:
```bash
bun test && bun run test:integration && npx playwright test
```

From `cli/`:
```bash
uv run pytest
```

Expected:
- Forge unit: 296+ pass, 0 fail
- Forge integration: 57+ pass, 0 fail
- Playwright E2E: 22+ pass (20 component + 2 cross-component), 0 fail
- CLI: 357+ pass, ≥90% coverage

- [ ] **Final commit**

```bash
git add forge/e2e/cross-component.spec.ts forge/e2e/cli-helper.ts
git commit -m "test: complete cross-component E2E harness — CLI + Forge integration verified"
```
