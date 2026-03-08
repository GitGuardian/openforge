# Phase 4: Automated Indexing & CLI Parity — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automate plugin indexing via GitHub webhooks, add CLI staleness detection and update capabilities, expand source support (GitLab, SSH, local, well-known), and enable remote plugin discovery from the Forge.

**Architecture:** Three steel threads delivered incrementally. Thread 1 is the skateboard (webhook → index → check). Thread 2 widens CLI reach (update, providers, sources). Thread 3 closes the discovery loop (remote find). Both teammates work in parallel within each thread; end-to-end testing gates the thread.

**Tech Stack:** Forge: Bun + Hono + Drizzle + Supabase. CLI: Python 3.10+ + Typer + Rich. Git operations via subprocess. HTTP via standard library.

---

## Thread 1: "Git push → Forge knows → CLI detects staleness"

### Task 1: Forge — Schema migration for skills table

**Owner:** forge-dev

**Files:**
- Modify: `forge/src/db/schema.ts`
- Create: `forge/drizzle/0002_skills_phase4.sql`
- Modify: `forge/drizzle/meta/_journal.json`

**Step 1: Update Drizzle schema**

Add `updatedAt`, `status`, and unique constraint to `skills` table in `schema.ts`:

```typescript
// In the skills table definition, add:
updatedAt: timestamp("updated_at", { withTimezone: true }).defaultNow().notNull(),
status: text("status").notNull().default("active"),

// Add to the table's third argument (constraints):
(table) => [unique("skills_registry_path").on(table.registryId, table.skillMdPath)]
```

**Step 2: Write migration SQL**

Create `forge/drizzle/0002_skills_phase4.sql`:

```sql
ALTER TABLE "skills" ADD COLUMN "updated_at" timestamptz DEFAULT now() NOT NULL;
ALTER TABLE "skills" ADD COLUMN "status" text DEFAULT 'active' NOT NULL;
ALTER TABLE "skills" ADD CONSTRAINT "skills_registry_path" UNIQUE ("registry_id", "skill_md_path");
```

**Step 3: Update journal**

Add entry to `_journal.json`:
```json
{ "idx": 2, "version": "7", "when": 1773004800000, "tag": "0002_skills_phase4", "breakpoints": true }
```

**Step 4: Run typecheck and apply migration**

```bash
cd forge && bun run typecheck
bun run db:push  # or apply migration manually via supabase
```

**Step 5: Commit**

```bash
git add forge/src/db/schema.ts forge/drizzle/0002_skills_phase4.sql forge/drizzle/meta/_journal.json
git commit -m "feat(forge): add skills table unique constraint, updated_at, and status columns"
```

---

### Task 2: Forge — Extract indexer library from seed.ts

**Owner:** forge-dev

**Files:**
- Create: `forge/src/lib/indexer.ts`
- Reference: `forge/src/scripts/seed.ts` (current implementation to extract from)

**Step 1: Create indexer.ts with extracted functions**

Move these functions from `seed.ts` into `forge/src/lib/indexer.ts`:
- `cloneRepo(url: string): Promise<string>` — shallow clone to tmpdir
- `getHeadSha(repoDir: string): Promise<string>` — git rev-parse HEAD
- `findFiles(dir: string, pattern: RegExp): Promise<string[]>` — recursive scan
- `parseFrontmatter(content: string): SkillFrontmatter` — YAML frontmatter
- `parsePlugin(pluginJsonPath: string, repoRoot: string): Promise<PluginData | null>` — plugin.json + README
- `parseMarketplace(marketplacePath: string, repoRoot: string): Promise<PluginData[]>` — marketplace.json

Add the main entry point:

```typescript
export interface IndexResult {
  pluginsFound: number;
  skillsFound: number;
  pluginsRemoved: number;
  skillsRemoved: number;
  errors: string[];
}

export async function indexRegistry(registryId: string): Promise<IndexResult> {
  // 1. Look up registry by ID, get git_url
  // 2. Clone repo (shallow)
  // 3. Get HEAD SHA
  // 4. Scan for plugin.json, marketplace.json, SKILL.md
  // 5. Parse and deduplicate (existing logic from seed.ts)
  // 6. Upsert plugins (ON CONFLICT DO UPDATE)
  // 7. Upsert skills (now with ON CONFLICT using new unique constraint)
  // 8. Detect stale content: query all plugins/skills for this registry,
  //    mark any not found in latest scan as status = 'removed'
  // 9. Update registries.indexed_at = now()
  // 10. Cleanup temp dir
  // 11. Return IndexResult
}
```

**Stale content detection logic:**

```typescript
// After upserting, get all plugin names found in this scan
const foundPluginNames = new Set(parsedPlugins.map(p => p.name));
// Mark plugins in this registry not in foundPluginNames as 'removed'
await db.update(plugins)
  .set({ status: "removed", updatedAt: new Date() })
  .where(
    and(
      eq(plugins.registryId, registryId),
      notInArray(plugins.name, [...foundPluginNames]),
      ne(plugins.status, "removed")
    )
  );
// Same for skills using foundSkillPaths
```

**Skill upsert** now uses `ON CONFLICT` instead of select+insert:

```typescript
await db.insert(skills).values({
  registryId, pluginId, name, description, skillMdPath, metadata,
  updatedAt: new Date(), status: "active",
}).onConflictDoUpdate({
  target: [skills.registryId, skills.skillMdPath],
  set: { name, description, metadata, pluginId, updatedAt: new Date(), status: "active" },
});
```

**Step 2: Typecheck**

```bash
cd forge && bun run typecheck
```

**Step 3: Commit**

```bash
git add forge/src/lib/indexer.ts
git commit -m "feat(forge): extract indexer library from seed script"
```

---

### Task 3: Forge — Refactor seed.ts to use indexer

**Owner:** forge-dev

**Files:**
- Modify: `forge/src/scripts/seed.ts`

**Step 1: Refactor seed.ts to thin wrapper**

Replace the bulk of `main()` with calls to the indexer:

```typescript
import { indexRegistry } from "../lib/indexer";

async function main() {
  const { repo, name } = parseArgs(process.argv.slice(2));

  // Upsert registry (keep this in seed.ts — it's CLI-specific)
  const [registry] = await db.insert(registries).values({
    name, gitUrl: repo, registryType: "github",
  }).onConflictDoUpdate({
    target: registries.name,
    set: { gitUrl: repo },
  }).returning();

  // Delegate to indexer
  const result = await indexRegistry(registry.id);

  console.log(`Indexed: ${result.pluginsFound} plugins, ${result.skillsFound} skills`);
  if (result.pluginsRemoved > 0 || result.skillsRemoved > 0) {
    console.log(`Removed: ${result.pluginsRemoved} plugins, ${result.skillsRemoved} skills`);
  }
  if (result.errors.length > 0) {
    console.error(`Errors: ${result.errors.join(", ")}`);
  }
  process.exit(0);
}
```

**Step 2: Smoke test — re-run seed against test repo**

```bash
cd forge && bun run seed -- --repo https://github.com/<owner>/cc-marketplace --name test-marketplace
```

Verify plugins and skills are indexed correctly (check via Supabase Studio or `bun run dev` and browse catalogue).

**Step 3: Typecheck**

```bash
bun run typecheck
```

**Step 4: Commit**

```bash
git add forge/src/scripts/seed.ts
git commit -m "refactor(forge): use indexer library in seed script"
```

---

### Task 4: Forge — Add webhook route with HMAC verification

**Owner:** forge-dev

**Files:**
- Create: `forge/src/routes/webhooks.ts`

**Step 1: Implement webhook route**

```typescript
import { Hono } from "hono";
import { timingSafeEqual } from "crypto";
import { eq } from "drizzle-orm";
import { db } from "../db";
import { registries } from "../db/schema";
import { indexRegistry } from "../lib/indexer";
import type { AppEnv } from "../types";

export const webhookRoutes = new Hono<AppEnv>();

function verifySignature(secret: string, payload: string, signature: string): boolean {
  const expected = `sha256=${Bun.CryptoHasher.hash("sha256", payload, "hex")}`;
  // Use HMAC, not plain hash:
  const hmac = new Bun.CryptoHasher("sha256", secret);
  hmac.update(payload);
  const expectedSig = `sha256=${hmac.digest("hex")}`;

  if (signature.length !== expectedSig.length) return false;
  return timingSafeEqual(
    Buffer.from(signature),
    Buffer.from(expectedSig)
  );
}

webhookRoutes.post("/api/webhooks/github", async (c) => {
  const event = c.req.header("X-GitHub-Event");
  if (event !== "push") {
    return c.json({ message: "ignored event" }, 200);
  }

  const rawBody = await c.req.text();
  const signature = c.req.header("X-Hub-Signature-256");
  if (!signature) {
    return c.json({ error: "missing signature" }, 401);
  }

  // Parse payload to find repo URL
  let payload: { repository?: { clone_url?: string; html_url?: string }; ref?: string };
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return c.json({ error: "invalid JSON" }, 400);
  }

  // Only process pushes to default branch
  const ref = payload.ref;
  if (!ref?.startsWith("refs/heads/")) {
    return c.json({ message: "ignored non-branch ref" }, 200);
  }

  const repoUrl = payload.repository?.clone_url || payload.repository?.html_url;
  if (!repoUrl) {
    return c.json({ error: "no repository URL in payload" }, 400);
  }

  // Find matching registry
  const allRegistries = await db.select().from(registries);
  const registry = allRegistries.find(
    (r) => repoUrl.includes(r.gitUrl.replace(/\.git$/, "")) || r.gitUrl.includes(repoUrl.replace(/\.git$/, ""))
  );
  if (!registry) {
    return c.json({ error: "no matching registry" }, 404);
  }

  // Verify HMAC signature
  if (!registry.webhookSecret) {
    return c.json({ error: "registry has no webhook secret configured" }, 403);
  }
  if (!verifySignature(registry.webhookSecret, rawBody, signature)) {
    return c.json({ error: "invalid signature" }, 401);
  }

  // Concurrency guard: skip if indexed less than 60s ago
  if (registry.indexedAt) {
    const elapsed = Date.now() - new Date(registry.indexedAt).getTime();
    if (elapsed < 60_000) {
      return c.json({ message: "indexing already in progress" }, 200);
    }
  }

  // Mark as indexing now (before async work)
  await db.update(registries)
    .set({ indexedAt: new Date() })
    .where(eq(registries.id, registry.id));

  // Run indexing in background — don't block the response
  indexRegistry(registry.id)
    .then((result) => {
      console.log(`Webhook indexing complete for ${registry.name}:`, result);
    })
    .catch((err) => {
      console.error(`Webhook indexing failed for ${registry.name}:`, err);
    });

  return c.json({ message: "indexing started" }, 200);
});
```

**Step 2: Typecheck**

```bash
cd forge && bun run typecheck
```

**Step 3: Commit**

```bash
git add forge/src/routes/webhooks.ts
git commit -m "feat(forge): add GitHub webhook route with HMAC verification"
```

---

### Task 5: Forge — Wire webhook route into index.ts

**Owner:** forge-dev

**Files:**
- Modify: `forge/src/index.ts`

**Step 1: Register webhook route**

Import and register — webhook route must come BEFORE the CSRF middleware or use a CSRF exception. Since GitHub sends POST requests without CSRF tokens, the webhook route needs to bypass CSRF.

Approach: Register webhook route before the global `csrf()` middleware:

```typescript
import { webhookRoutes } from "./routes/webhooks";

// Register webhook route BEFORE csrf middleware (GitHub won't send CSRF token)
app.route("/", webhookRoutes);

// Then CSRF middleware
app.use("*", csrf());
```

Or alternatively, configure CSRF to exclude `/api/webhooks/*` paths. Check what's cleanest given the current middleware ordering.

**Step 2: Smoke test — simulate webhook**

```bash
# Generate HMAC signature for test payload
SECRET="test-secret-123"
PAYLOAD='{"ref":"refs/heads/main","repository":{"clone_url":"https://github.com/<owner>/cc-marketplace.git","html_url":"https://github.com/<owner>/cc-marketplace"}}'
SIG="sha256=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')"

# First, update registry to have webhook_secret (via Supabase Studio or SQL)
# Then send test webhook:
curl -X POST http://localhost:3000/api/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$PAYLOAD"
```

Expected: `{"message":"indexing started"}` with 200. Check Forge logs for indexing output.

**Step 3: Typecheck**

```bash
bun run typecheck
```

**Step 4: Commit**

```bash
git add forge/src/index.ts
git commit -m "feat(forge): register webhook route, bypass CSRF for webhooks"
```

---

### Task 6: CLI — Extend types for multi-provider support

**Owner:** cli-dev

**Files:**
- Modify: `cli/src/openforge/types.py`
- Test: `cli/tests/test_types.py`

**Step 1: Write tests for new SourceType values and Source extensions**

```python
def test_source_type_values():
    assert SourceType.GITHUB.value == "github"
    assert SourceType.GITLAB.value == "gitlab"
    assert SourceType.GIT.value == "git"
    assert SourceType.LOCAL.value == "local"
    assert SourceType.WELL_KNOWN.value == "well_known"
    assert SourceType.FORGE.value == "forge"

def test_source_git_url_github():
    s = Source(owner="acme", repo="skills")
    assert s.git_url == "https://github.com/acme/skills"

def test_source_git_url_explicit():
    s = Source(source_type=SourceType.GITLAB, url="https://gitlab.com/acme/skills")
    assert s.git_url == "https://gitlab.com/acme/skills"

def test_source_git_url_local():
    s = Source(source_type=SourceType.LOCAL, local_path="/tmp/my-plugin")
    assert s.local_path == "/tmp/my-plugin"
```

**Step 2: Run tests to verify they fail**

```bash
cd cli && python -m pytest tests/test_types.py -v -k "source_type_values or source_git_url"
```

**Step 3: Extend SourceType and Source**

```python
class SourceType(Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    GIT = "git"
    LOCAL = "local"
    WELL_KNOWN = "well_known"
    FORGE = "forge"

@dataclass(frozen=True)
class Source:
    source_type: SourceType = SourceType.GITHUB
    owner: str = ""
    repo: str = ""
    skill_name: str | None = None
    subdir: str | None = None
    ref: str | None = None
    url: str | None = None          # For GitLab, SSH, well-known, forge URLs
    local_path: str | None = None   # For local sources

    @property
    def shorthand(self) -> str:
        if self.source_type == SourceType.LOCAL:
            return self.local_path or ""
        if self.source_type in (SourceType.WELL_KNOWN, SourceType.FORGE):
            return self.url or ""
        base = f"{self.owner}/{self.repo}" if self.owner else (self.url or "")
        if self.skill_name:
            return f"{base}@{self.skill_name}"
        return base

    @property
    def git_url(self) -> str:
        if self.url:
            return self.url
        return f"https://github.com/{self.owner}/{self.repo}"
```

Keep `owner`/`repo` default to `""` instead of making them Optional to avoid breaking existing code that accesses these directly.

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_types.py -v
```

**Step 5: Run full test suite to check nothing broke**

```bash
python -m pytest --tb=short
```

**Step 6: Run pyright**

```bash
pyright
```

**Step 7: Commit**

```bash
git add cli/src/openforge/types.py cli/tests/test_types.py
git commit -m "feat(cli): extend Source and SourceType for multi-provider support"
```

---

### Task 7: CLI — Add `check` command

**Owner:** cli-dev

**Files:**
- Create: `cli/src/openforge/check.py`
- Create: `cli/tests/test_check.py`
- Modify: `cli/src/openforge/cli.py`

**Step 1: Write failing tests**

```python
# tests/test_check.py
from unittest.mock import patch, MagicMock
from openforge.check import check_command, check_entry_staleness
from openforge.types import LockEntry, ContentType, SourceType

def _make_entry(git_url="https://github.com/acme/skills", git_sha="abc123") -> LockEntry:
    return LockEntry(
        type=ContentType.SKILL,
        source="acme/skills",
        source_type=SourceType.GITHUB,
        git_url=git_url,
        git_sha=git_sha,
        skills=("my-skill",),
        agents_installed=("claude-code",),
        installed_at="2026-03-01T00:00:00Z",
        updated_at="2026-03-01T00:00:00Z",
    )

@patch("openforge.check._git_ls_remote")
def test_check_entry_up_to_date(mock_ls_remote):
    mock_ls_remote.return_value = "abc123"
    entry = _make_entry(git_sha="abc123")
    result = check_entry_staleness("acme/skills", entry)
    assert result.is_outdated is False
    assert result.remote_sha == "abc123"

@patch("openforge.check._git_ls_remote")
def test_check_entry_outdated(mock_ls_remote):
    mock_ls_remote.return_value = "def456"
    entry = _make_entry(git_sha="abc123")
    result = check_entry_staleness("acme/skills", entry)
    assert result.is_outdated is True
    assert result.local_sha == "abc123"
    assert result.remote_sha == "def456"

@patch("openforge.check._git_ls_remote")
def test_check_entry_unreachable(mock_ls_remote):
    mock_ls_remote.side_effect = subprocess.CalledProcessError(128, "git")
    entry = _make_entry()
    result = check_entry_staleness("acme/skills", entry)
    assert result.is_outdated is False
    assert result.error is not None
```

**Step 2: Run tests to verify they fail**

```bash
cd cli && python -m pytest tests/test_check.py -v
```

**Step 3: Implement check.py**

```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from openforge.lock import lock_file_path, read_lock
from openforge.telemetry import send_event
from openforge.types import SourceType

_console = Console()

@dataclass(frozen=True)
class CheckResult:
    name: str
    local_sha: str
    remote_sha: str
    is_outdated: bool
    error: str | None = None

def _git_ls_remote(git_url: str, ref: str | None = None) -> str:
    """Get remote HEAD SHA without cloning."""
    target = ref or "HEAD"
    result = subprocess.run(
        ["git", "ls-remote", git_url, target],
        check=True, capture_output=True, text=True,
    )  # nosec
    # Output format: "sha\tref\n"
    line = result.stdout.strip().split("\n")[0]
    if not line:
        msg = f"no ref found for {target}"
        raise ValueError(msg)
    return line.split("\t")[0]

def check_entry_staleness(name: str, entry: object) -> CheckResult:
    """Check if a single lock entry is outdated."""
    from openforge.types import LockEntry
    assert isinstance(entry, LockEntry)

    if entry.source_type == SourceType.LOCAL:
        return CheckResult(name=name, local_sha="", remote_sha="", is_outdated=False,
                          error="local sources cannot be checked")
    if entry.source_type == SourceType.WELL_KNOWN:
        return CheckResult(name=name, local_sha="", remote_sha="", is_outdated=False,
                          error="well-known sources: check not yet supported")

    try:
        remote_sha = _git_ls_remote(entry.git_url)
    except (subprocess.CalledProcessError, ValueError) as exc:
        return CheckResult(name=name, local_sha=entry.git_sha, remote_sha="",
                          is_outdated=False, error=str(exc))

    return CheckResult(
        name=name,
        local_sha=entry.git_sha,
        remote_sha=remote_sha,
        is_outdated=entry.git_sha != remote_sha,
    )

def check_command(
    name: str | None = typer.Argument(None, help="Check a specific entry (default: all)"),
    is_global: bool = typer.Option(False, "--global", "-g", help="Check globally installed"),
) -> None:
    """Check installed plugins and skills for updates."""
    project_dir = Path.cwd()
    path = lock_file_path(project_dir, is_global=is_global)
    lock = read_lock(path)

    if not lock.entries:
        _console.print("[yellow]No installed plugins or skills.[/yellow]")
        raise typer.Exit()

    entries = {name: lock.entries[name]} if name else lock.entries
    if name and name not in lock.entries:
        _console.print(f"[red]Not found: {name}[/red]")
        raise typer.Exit(code=1)

    results: list[CheckResult] = []
    for entry_name, entry in entries.items():
        results.append(check_entry_staleness(entry_name, entry))

    # Display table
    table = Table(title="Update Check")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Installed")
    table.add_column("Remote")

    outdated_count = 0
    for r in results:
        if r.error:
            table.add_row(r.name, f"[yellow]error: {r.error}[/yellow]", "", "")
        elif r.is_outdated:
            outdated_count += 1
            table.add_row(r.name, "[red]outdated[/red]", r.local_sha[:8], r.remote_sha[:8])
        else:
            table.add_row(r.name, "[green]up to date[/green]", r.local_sha[:8], r.remote_sha[:8])

    _console.print(table)

    if outdated_count:
        _console.print(f"\n[yellow]{outdated_count} outdated. Run 'openforge update' to update.[/yellow]")
    else:
        _console.print("\n[green]All up to date.[/green]")

    send_event("check", {"entries_checked": len(results), "outdated": outdated_count})
```

**Step 4: Register command in cli.py**

Add to `_build_app()`:

```python
from openforge.check import check_command
app.command("check")(check_command)
```

**Step 5: Run tests**

```bash
python -m pytest tests/test_check.py -v
python -m pytest --tb=short  # full suite
pyright
```

**Step 6: Commit**

```bash
git add cli/src/openforge/check.py cli/tests/test_check.py cli/src/openforge/cli.py
git commit -m "feat(cli): add check command for staleness detection"
```

---

### Task 8: Manual E2E — Thread 1 verification

**Owner:** team-lead (with both agents)

**Prerequisites:** Tasks 1-7 complete, local Supabase running.

**Step 1: Start local environment**

```bash
cd forge/supabase && supabase start
cd forge && bun run dev
```

**Step 2: Seed from test marketplace repo**

```bash
cd forge && bun run seed -- --repo https://github.com/<owner>/cc-marketplace --name test-marketplace
```

Verify plugins appear in the catalogue at `http://localhost:3000`.

**Step 3: Set webhook secret on registry**

Via Supabase Studio (`http://127.0.0.1:54323`) or direct SQL:

```sql
UPDATE registries SET webhook_secret = 'test-secret-123' WHERE name = 'test-marketplace';
```

**Step 4: Simulate GitHub webhook**

```bash
SECRET="test-secret-123"
PAYLOAD='{"ref":"refs/heads/main","repository":{"clone_url":"https://github.com/<owner>/cc-marketplace.git"}}'
SIG="sha256=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | awk '{print $2}')"

curl -X POST http://localhost:3000/api/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: $SIG" \
  -d "$PAYLOAD"
```

Expected: `{"message":"indexing started"}`. Check Forge logs for successful indexing.

**Step 5: Verify HMAC rejection**

```bash
curl -X POST http://localhost:3000/api/webhooks/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: push" \
  -H "X-Hub-Signature-256: sha256=bad" \
  -d "$PAYLOAD"
```

Expected: `{"error":"invalid signature"}` with 401.

**Step 6: Test CLI check**

```bash
cd /tmp && mkdir test-project && cd test-project
uvx openforge add <owner>/cc-marketplace
uvx openforge check
```

Expected: table showing installed entries with "up to date" or "outdated" status.

**Step 7: Commit any fixes, then push**

```bash
git push
```

---

## Thread 2: "CLI can update and install from anywhere"

### Task 9: CLI — Add `update` command

**Owner:** cli-dev

**Files:**
- Create: `cli/src/openforge/update.py`
- Create: `cli/tests/test_update.py`
- Modify: `cli/src/openforge/cli.py`

**Step 1: Write failing tests**

```python
# tests/test_update.py
from unittest.mock import patch, MagicMock, call
from openforge.update import update_command

@patch("openforge.update.check_entry_staleness")
@patch("openforge.update.read_lock")
@patch("openforge.update.lock_file_path")
def test_update_skips_up_to_date(mock_path, mock_read, mock_check):
    """Update with no outdated entries prints 'all up to date'."""
    from openforge.check import CheckResult
    mock_path.return_value = Path("/tmp/lock.json")
    mock_read.return_value = LockFile(entries={"acme/skills": _make_entry()})
    mock_check.return_value = CheckResult(
        name="acme/skills", local_sha="abc", remote_sha="abc", is_outdated=False
    )
    # Should not raise, should print "all up to date"
    # (test via captured output or mock console)

@patch("openforge.update._reinstall_entry")
@patch("openforge.update.check_entry_staleness")
@patch("openforge.update.read_lock")
@patch("openforge.update.lock_file_path")
def test_update_reinstalls_outdated(mock_path, mock_read, mock_check, mock_reinstall):
    """Update with outdated entry triggers reinstall."""
    from openforge.check import CheckResult
    mock_path.return_value = Path("/tmp/lock.json")
    mock_read.return_value = LockFile(entries={"acme/skills": _make_entry()})
    mock_check.return_value = CheckResult(
        name="acme/skills", local_sha="abc", remote_sha="def", is_outdated=True
    )
    mock_reinstall.return_value = None
    update_command(name=None, is_global=False, yes=True)
    mock_reinstall.assert_called_once()
```

**Step 2: Run tests to verify they fail**

```bash
cd cli && python -m pytest tests/test_update.py -v
```

**Step 3: Implement update.py**

```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import tempfile
from pathlib import Path

import typer
from rich.console import Console

from openforge.check import check_entry_staleness
from openforge.lock import add_lock_entry, lock_file_path, read_lock
from openforge.providers.github import GitHubProvider
from openforge.providers.source_parser import parse_source
from openforge.installer import create_canonical_storage, install_to_all_agents
from openforge.plugins import detect_content
from openforge.telemetry import send_event
from openforge.types import ContentType, LockEntry

_console = Console()

def _reinstall_entry(name: str, entry: LockEntry, project_dir: Path, is_global: bool) -> None:
    """Re-run the add flow for a single outdated entry."""
    source = parse_source(entry.source)
    provider = GitHubProvider()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "repo"
        new_sha = provider.fetch(source, tmp_path)
        content_root = provider.content_root(source, tmp_path)
        detected = detect_content(content_root)

        # Show what changed
        old_skills = set(entry.skills)
        new_skills = {s.name for s in detected.skills}
        added = new_skills - old_skills
        removed = old_skills - new_skills
        if added:
            _console.print(f"  [green]+ {len(added)} new skills: {', '.join(sorted(added))}[/green]")
        if removed:
            _console.print(f"  [red]- {len(removed)} removed skills: {', '.join(sorted(removed))}[/red]")
        if not added and not removed:
            _console.print("  [dim]Content updated (no skill changes)[/dim]")

        # Reinstall
        for skill in detected.skills:
            create_canonical_storage(
                content_root / skill.path, project_dir, skill.name,
                ContentType.SKILL, is_global,
            )
        agents = install_to_all_agents(
            detected.skills, project_dir, ContentType.SKILL, is_global, target_agent=None,
        )

        # Update lock
        from datetime import datetime, timezone
        new_entry = LockEntry(
            type=entry.type,
            source=entry.source,
            source_type=entry.source_type,
            git_url=entry.git_url,
            git_sha=new_sha,
            skills=tuple(s.name for s in detected.skills),
            agents_installed=tuple(agents),
            installed_at=entry.installed_at,
            updated_at=datetime.now(tz=timezone.utc).isoformat(),
        )
        lock_path = lock_file_path(project_dir, is_global=is_global)
        add_lock_entry(lock_path, name, new_entry)

def update_command(
    name: str | None = typer.Argument(None, help="Update a specific entry (default: all)"),
    is_global: bool = typer.Option(False, "--global", "-g", help="Update globally installed"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm"),
) -> None:
    """Update outdated plugins and skills."""
    project_dir = Path.cwd()
    path = lock_file_path(project_dir, is_global=is_global)
    lock = read_lock(path)

    if not lock.entries:
        _console.print("[yellow]No installed plugins or skills.[/yellow]")
        raise typer.Exit()

    entries = {name: lock.entries[name]} if name else lock.entries
    if name and name not in lock.entries:
        _console.print(f"[red]Not found: {name}[/red]")
        raise typer.Exit(code=1)

    # Check staleness
    outdated = []
    for entry_name, entry in entries.items():
        result = check_entry_staleness(entry_name, entry)
        if result.is_outdated:
            outdated.append((entry_name, entry))

    if not outdated:
        _console.print("[green]All up to date.[/green]")
        raise typer.Exit()

    _console.print(f"[yellow]{len(outdated)} outdated:[/yellow]")
    for entry_name, _ in outdated:
        _console.print(f"  - {entry_name}")

    if not yes:
        confirm = typer.confirm("Update all?")
        if not confirm:
            raise typer.Exit()

    for entry_name, entry in outdated:
        _console.print(f"\n[bold]Updating {entry_name}...[/bold]")
        _reinstall_entry(entry_name, entry, project_dir, is_global)
        _console.print(f"[green]Updated {entry_name}[/green]")

    send_event("update", {"entries_updated": len(outdated)})
    _console.print(f"\n[green]Updated {len(outdated)} entries.[/green]")
```

**Step 4: Register in cli.py**

```python
from openforge.update import update_command
app.command("update")(update_command)
```

**Step 5: Run tests**

```bash
python -m pytest tests/test_update.py -v
python -m pytest --tb=short
pyright
```

**Step 6: Commit**

```bash
git add cli/src/openforge/update.py cli/tests/test_update.py cli/src/openforge/cli.py
git commit -m "feat(cli): add update command for outdated entries"
```

---

### Task 10: CLI — Create Provider protocol and GitProvider

**Owner:** cli-dev

**Files:**
- Create: `cli/src/openforge/providers/base.py`
- Create: `cli/src/openforge/providers/git.py`
- Create: `cli/tests/test_providers_git.py`

**Step 1: Write tests for GitProvider**

```python
# tests/test_providers_git.py
from openforge.providers.git import GitProvider
from openforge.providers.base import FetchResult
from openforge.types import Source, SourceType

def test_git_provider_matches_github():
    p = GitProvider()
    s = Source(source_type=SourceType.GITHUB, owner="acme", repo="skills")
    assert p.matches(s) is True

def test_git_provider_matches_gitlab():
    p = GitProvider()
    s = Source(source_type=SourceType.GITLAB, url="https://gitlab.com/acme/skills")
    assert p.matches(s) is True

def test_git_provider_matches_git():
    p = GitProvider()
    s = Source(source_type=SourceType.GIT, url="git@github.com:acme/skills.git")
    assert p.matches(s) is True

def test_git_provider_no_match_local():
    p = GitProvider()
    s = Source(source_type=SourceType.LOCAL, local_path="/tmp/foo")
    assert p.matches(s) is False
```

**Step 2: Run tests to fail**

```bash
cd cli && python -m pytest tests/test_providers_git.py -v
```

**Step 3: Implement Provider protocol in base.py**

```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openforge.types import Source

@dataclass(frozen=True)
class FetchResult:
    sha: str               # Git SHA or content hash
    content_root: Path     # Path to the fetched content

class Provider(Protocol):
    def matches(self, source: Source) -> bool: ...
    def fetch(self, source: Source, dest: Path) -> FetchResult: ...
```

**Step 4: Implement GitProvider in git.py**

Extract logic from `GitHubProvider` into a more general `GitProvider` that handles GitHub, GitLab, SSH, and generic git URLs — all via `git clone`:

```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from openforge.providers.base import FetchResult
from openforge.types import Source, SourceType
from openforge.validation import validate_path_containment

_GIT_SOURCE_TYPES = frozenset({SourceType.GITHUB, SourceType.GITLAB, SourceType.GIT})

class GitProvider:
    def matches(self, source: Source) -> bool:
        return source.source_type in _GIT_SOURCE_TYPES

    def fetch(self, source: Source, dest: Path) -> FetchResult:
        url = source.git_url
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

        cmd: list[str] = ["git", "clone", "--depth", "1"]
        env = {**os.environ}

        # Only inject token for GitHub/GitLab HTTPS URLs
        if token and url.startswith("https://"):
            cmd[1:1] = ["-c", f"http.extraheader=Authorization: Bearer {token}"]

        if source.ref:
            cmd.extend(["--branch", source.ref])

        cmd.extend([url, str(dest)])
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)  # nosec

        # Get HEAD SHA
        result = subprocess.run(
            ["git", "-C", str(dest), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        )  # nosec
        sha = result.stdout.strip()

        content_root = dest
        if source.subdir:
            content_root = dest / source.subdir
            validate_path_containment(content_root, dest)

        return FetchResult(sha=sha, content_root=content_root)
```

**Step 5: Run tests**

```bash
python -m pytest tests/test_providers_git.py -v
pyright
```

**Step 6: Commit**

```bash
git add cli/src/openforge/providers/base.py cli/src/openforge/providers/git.py cli/tests/test_providers_git.py
git commit -m "feat(cli): add Provider protocol and GitProvider"
```

---

### Task 11: CLI — Extend source parser for new source types

**Owner:** cli-dev

**Files:**
- Modify: `cli/src/openforge/providers/source_parser.py`
- Create: `cli/tests/test_source_parser_extended.py`

**Step 1: Write tests for new source formats**

```python
# tests/test_source_parser_extended.py
from openforge.providers.source_parser import parse_source
from openforge.types import SourceType

# GitLab URLs
def test_parse_gitlab_url():
    s = parse_source("https://gitlab.com/acme/skills")
    assert s.source_type == SourceType.GITLAB
    assert s.url == "https://gitlab.com/acme/skills"

def test_parse_gitlab_subgroup():
    s = parse_source("https://gitlab.com/group/subgroup/repo")
    assert s.source_type == SourceType.GITLAB
    assert s.url == "https://gitlab.com/group/subgroup/repo"

def test_parse_gitlab_prefix():
    s = parse_source("gitlab:acme/skills")
    assert s.source_type == SourceType.GITLAB
    assert s.url == "https://gitlab.com/acme/skills"

# SSH URLs
def test_parse_ssh_url():
    s = parse_source("git@github.com:acme/skills.git")
    assert s.source_type == SourceType.GIT
    assert s.url == "git@github.com:acme/skills.git"

def test_parse_ssh_gitlab():
    s = parse_source("git@gitlab.com:acme/skills.git")
    assert s.source_type == SourceType.GIT
    assert s.url == "git@gitlab.com:acme/skills.git"

# Local paths
def test_parse_local_relative():
    s = parse_source("./my-plugin")
    assert s.source_type == SourceType.LOCAL
    assert s.local_path == "./my-plugin"

def test_parse_local_absolute():
    s = parse_source("/tmp/my-plugin")
    assert s.source_type == SourceType.LOCAL
    assert s.local_path == "/tmp/my-plugin"

def test_parse_local_parent():
    s = parse_source("../my-plugin")
    assert s.source_type == SourceType.LOCAL
    assert s.local_path == "../my-plugin"

# Branch refs
def test_parse_github_with_branch():
    s = parse_source("acme/skills#develop")
    assert s.source_type == SourceType.GITHUB
    assert s.owner == "acme"
    assert s.repo == "skills"
    assert s.ref == "develop"

def test_parse_github_with_skill_and_branch():
    s = parse_source("acme/skills@my-skill#v2")
    assert s.source_type == SourceType.GITHUB
    assert s.skill_name == "my-skill"
    assert s.ref == "v2"

# Well-known
def test_parse_well_known_url():
    s = parse_source("https://mintlify.com/docs")
    assert s.source_type == SourceType.WELL_KNOWN
    assert s.url == "https://mintlify.com/docs"

# Forge
def test_parse_forge_prefix():
    s = parse_source("forge:my-plugin")
    assert s.source_type == SourceType.FORGE
    assert s.url == "my-plugin"
```

**Step 2: Run tests to fail**

```bash
cd cli && python -m pytest tests/test_source_parser_extended.py -v
```

**Step 3: Extend parse_source()**

Add new regex patterns and update `parse_source()`:

```python
_GITLAB_URL_RE = re.compile(
    r"^https://gitlab\.com/(?P<path>[a-zA-Z0-9_./-]+?)(?:\.git)?(?:/-/tree/(?P<ref>[^/]+)(?:/(?P<subdir>.+))?)?/?$"
)
_GITLAB_PREFIX_RE = re.compile(r"^gitlab:(?P<path>[a-zA-Z0-9_./-]+)$")
_SSH_RE = re.compile(r"^git@[a-zA-Z0-9_.:-]+:[a-zA-Z0-9_./-]+(?:\.git)?$")
_LOCAL_PATH_RE = re.compile(r"^(?:\./|/|\.\./).*$")
_BRANCH_RE = re.compile(r"#(?P<ref>[^#]+)$")
_FORGE_PREFIX_RE = re.compile(r"^forge:(?P<name>.+)$")

def parse_source(raw: str) -> Source:
    # 1. Check for forge: prefix
    m = _FORGE_PREFIX_RE.match(raw)
    if m:
        return Source(source_type=SourceType.FORGE, url=m.group("name"))

    # 2. Check for gitlab: prefix
    m = _GITLAB_PREFIX_RE.match(raw)
    if m:
        return Source(source_type=SourceType.GITLAB, url=f"https://gitlab.com/{m.group('path')}")

    # 3. Check for local paths
    if _LOCAL_PATH_RE.match(raw):
        return Source(source_type=SourceType.LOCAL, local_path=raw)

    # 4. Extract branch ref (before other parsing)
    ref_from_hash = None
    m = _BRANCH_RE.search(raw)
    if m:
        ref_from_hash = m.group("ref")
        raw = raw[:m.start()]  # strip #ref suffix

    # 5. Check for SSH URLs
    if _SSH_RE.match(raw):
        return Source(source_type=SourceType.GIT, url=raw, ref=ref_from_hash)

    # 6. Check for GitLab URLs
    m = _GITLAB_URL_RE.match(raw)
    if m:
        return Source(source_type=SourceType.GITLAB, url=raw, ref=m.group("ref") or ref_from_hash, subdir=m.group("subdir"))

    # 7. Check for GitHub URLs (existing logic)
    m = _GITHUB_URL_RE.match(raw)
    if m:
        return Source(owner=m.group("owner"), repo=m.group("repo"),
                     ref=m.group("ref") or ref_from_hash, subdir=m.group("subdir"))

    # 8. Check for well-known HTTPS URLs (non-GitHub, non-GitLab)
    if raw.startswith("https://"):
        return Source(source_type=SourceType.WELL_KNOWN, url=raw)

    # 9. GitHub shorthand (existing logic, with #ref support)
    m = _SHORTHAND_RE.match(raw)
    if m:
        return Source(owner=m.group("owner"), repo=m.group("repo"),
                     skill_name=m.group("skill"), subdir=m.group("subdir"),
                     ref=ref_from_hash)

    msg = f"cannot parse source: {raw}"
    raise ValueError(msg)
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_source_parser_extended.py -v
python -m pytest --tb=short  # full suite
pyright
```

**Step 5: Commit**

```bash
git add cli/src/openforge/providers/source_parser.py cli/tests/test_source_parser_extended.py
git commit -m "feat(cli): extend source parser for GitLab, SSH, local, branch refs, well-known, forge"
```

---

### Task 12: CLI — Add LocalProvider

**Owner:** cli-dev

**Files:**
- Create: `cli/src/openforge/providers/local.py`
- Create: `cli/tests/test_providers_local.py`

**Step 1: Write tests**

```python
# tests/test_providers_local.py
import pytest
from pathlib import Path
from openforge.providers.local import LocalProvider
from openforge.types import Source, SourceType

def test_local_provider_matches():
    p = LocalProvider()
    s = Source(source_type=SourceType.LOCAL, local_path="/tmp/foo")
    assert p.matches(s) is True

def test_local_provider_no_match_github():
    p = LocalProvider()
    s = Source(source_type=SourceType.GITHUB, owner="acme", repo="skills")
    assert p.matches(s) is False

def test_local_provider_fetch(tmp_path):
    # Create a skill in tmp_path
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n# My Skill")

    p = LocalProvider()
    s = Source(source_type=SourceType.LOCAL, local_path=str(tmp_path))
    result = p.fetch(s, Path("/unused"))  # dest unused for local
    assert result.content_root == tmp_path
    assert result.sha != ""  # should be a content hash

def test_local_provider_fetch_nonexistent():
    p = LocalProvider()
    s = Source(source_type=SourceType.LOCAL, local_path="/nonexistent/path")
    with pytest.raises(FileNotFoundError):
        p.fetch(s, Path("/unused"))
```

**Step 2: Run tests to fail, then implement**

```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
from pathlib import Path

from openforge.providers.base import FetchResult
from openforge.types import Source, SourceType

class LocalProvider:
    def matches(self, source: Source) -> bool:
        return source.source_type == SourceType.LOCAL

    def fetch(self, source: Source, dest: Path) -> FetchResult:
        local_path = Path(source.local_path or "").resolve()
        if not local_path.exists():
            msg = f"local path does not exist: {local_path}"
            raise FileNotFoundError(msg)
        # Content hash for lock file (hash of all file paths + mtimes)
        hasher = hashlib.sha256()
        for f in sorted(local_path.rglob("*")):
            if f.is_file():
                hasher.update(str(f.relative_to(local_path)).encode())
                hasher.update(str(f.stat().st_mtime_ns).encode())
        return FetchResult(sha=hasher.hexdigest()[:12], content_root=local_path)
```

**Step 3: Run tests and pyright**

```bash
python -m pytest tests/test_providers_local.py -v
pyright
```

**Step 4: Commit**

```bash
git add cli/src/openforge/providers/local.py cli/tests/test_providers_local.py
git commit -m "feat(cli): add LocalProvider for local path sources"
```

---

### Task 13: CLI — Refactor add.py to use provider dispatch

**Owner:** cli-dev

**Files:**
- Modify: `cli/src/openforge/add.py`
- Modify existing tests to ensure nothing breaks

**Step 1: Create provider registry and dispatch**

Replace the hardcoded `GitHubProvider()` usage in `add_command` with provider dispatch:

```python
from openforge.providers.git import GitProvider
from openforge.providers.local import LocalProvider
from openforge.providers.base import FetchResult

_PROVIDERS = [GitProvider(), LocalProvider()]
# WellKnownProvider and ForgeProvider added in later tasks

def _get_provider(source: Source):
    for p in _PROVIDERS:
        if p.matches(source):
            return p
    msg = f"no provider for source type: {source.source_type.value}"
    raise ValueError(msg)
```

Update `add_command` to use dispatch:

```python
# Replace:
#   provider = GitHubProvider()
#   git_sha = provider.fetch(parsed, tmp_dir)
#   content_root = provider.content_root(parsed, tmp_dir)
# With:
provider = _get_provider(parsed)
result = provider.fetch(parsed, tmp_path)
content_root = result.content_root
git_sha = result.sha
```

Also update `_reinstall_entry` in `update.py` to use the same dispatch.

**Step 2: Run full test suite**

```bash
python -m pytest --tb=short
pyright
```

All existing tests must pass — the GitProvider handles the same GitHub sources that GitHubProvider did.

**Step 3: Commit**

```bash
git add cli/src/openforge/add.py cli/src/openforge/update.py
git commit -m "refactor(cli): use provider dispatch in add and update commands"
```

---

### Task 14: CLI — Add WellKnownProvider

**Owner:** cli-dev

**Files:**
- Create: `cli/src/openforge/providers/wellknown.py`
- Create: `cli/tests/test_providers_wellknown.py`
- Modify: `cli/src/openforge/add.py` (add to `_PROVIDERS`)

**Step 1: Write tests with mocked HTTP**

```python
# tests/test_providers_wellknown.py
from unittest.mock import patch, MagicMock
import json
from openforge.providers.wellknown import WellKnownProvider
from openforge.types import Source, SourceType

MOCK_INDEX = {
    "version": "1.0.0",
    "skills": [
        {
            "name": "my-skill",
            "description": "A test skill",
            "files": ["SKILL.md", "README.md"],
        }
    ],
}

MOCK_SKILL_MD = "---\nname: my-skill\ndescription: A test skill\n---\n# My Skill"

def test_wellknown_matches():
    p = WellKnownProvider()
    s = Source(source_type=SourceType.WELL_KNOWN, url="https://example.com")
    assert p.matches(s) is True

@patch("openforge.providers.wellknown._http_get")
def test_wellknown_fetch(mock_get, tmp_path):
    def side_effect(url):
        if "index.json" in url:
            return json.dumps(MOCK_INDEX)
        if "SKILL.md" in url:
            return MOCK_SKILL_MD
        return ""

    mock_get.side_effect = side_effect

    p = WellKnownProvider()
    s = Source(source_type=SourceType.WELL_KNOWN, url="https://example.com")
    result = p.fetch(s, tmp_path)
    assert (result.content_root / "my-skill" / "SKILL.md").exists()
    assert result.sha != ""

@patch("openforge.providers.wellknown._http_get")
def test_wellknown_no_index(mock_get, tmp_path):
    mock_get.side_effect = Exception("404")
    p = WellKnownProvider()
    s = Source(source_type=SourceType.WELL_KNOWN, url="https://example.com")
    with pytest.raises(ValueError, match="could not fetch"):
        p.fetch(s, tmp_path)
```

**Step 2: Implement WellKnownProvider**

```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

from openforge.providers.base import FetchResult
from openforge.types import Source, SourceType

_MAX_FILE_SIZE = 1_000_000  # 1MB per file

def _http_get(url: str) -> str:
    req = Request(url, headers={"User-Agent": "openforge-cli"})  # noqa: S310
    with urlopen(req, timeout=30) as resp:  # noqa: S310
        return resp.read(_MAX_FILE_SIZE).decode()

class WellKnownProvider:
    def matches(self, source: Source) -> bool:
        return source.source_type == SourceType.WELL_KNOWN

    def fetch(self, source: Source, dest: Path) -> FetchResult:
        base_url = (source.url or "").rstrip("/")

        # Try /.well-known/skills/index.json
        index_url = f"{base_url}/.well-known/skills/index.json"
        try:
            raw = _http_get(index_url)
        except (URLError, OSError) as exc:
            msg = f"could not fetch well-known index from {index_url}: {exc}"
            raise ValueError(msg) from exc

        index = json.loads(raw)
        skills_data = index.get("skills", [])
        if not skills_data:
            msg = f"no skills found in index at {index_url}"
            raise ValueError(msg)

        hasher = hashlib.sha256()
        dest.mkdir(parents=True, exist_ok=True)

        for skill in skills_data:
            name = skill.get("name", "")
            files = skill.get("files", ["SKILL.md"])
            skill_dir = dest / name
            skill_dir.mkdir(parents=True, exist_ok=True)

            for fname in files:
                file_url = f"{base_url}/.well-known/skills/{name}/{fname}"
                try:
                    content = _http_get(file_url)
                except (URLError, OSError):
                    if fname == "SKILL.md":
                        raise  # SKILL.md is required
                    continue
                (skill_dir / fname).write_text(content)
                hasher.update(content.encode())

        return FetchResult(sha=hasher.hexdigest()[:12], content_root=dest)
```

**Step 3: Add to provider registry in add.py**

```python
from openforge.providers.wellknown import WellKnownProvider
_PROVIDERS = [GitProvider(), LocalProvider(), WellKnownProvider()]
```

**Step 4: Run tests and pyright**

```bash
python -m pytest tests/test_providers_wellknown.py -v
python -m pytest --tb=short
pyright
```

**Step 5: Commit**

```bash
git add cli/src/openforge/providers/wellknown.py cli/tests/test_providers_wellknown.py cli/src/openforge/add.py
git commit -m "feat(cli): add WellKnownProvider for HTTP-based skill discovery"
```

---

### Task 15: CLI — Extend lock file for non-git sources

**Owner:** cli-dev

**Files:**
- Modify: `cli/src/openforge/lock.py`
- Modify: `cli/src/openforge/types.py` (if needed)
- Modify: `cli/tests/test_lock.py`

**Step 1: Write tests for new source types in lock**

```python
def test_lock_entry_local_source():
    entry = LockEntry(
        type=ContentType.SKILL,
        source="./my-plugin",
        source_type=SourceType.LOCAL,
        git_url="",            # no git URL for local
        git_sha="abc123def4",  # content hash
        skills=("my-skill",),
        agents_installed=("claude-code",),
        installed_at="2026-03-08T00:00:00Z",
        updated_at="2026-03-08T00:00:00Z",
    )
    d = _entry_to_dict(entry)
    assert d["source_type"] == "local"
    restored = _dict_to_entry(d)
    assert restored == entry

def test_lock_entry_well_known_source():
    entry = LockEntry(
        type=ContentType.SKILL,
        source="https://example.com",
        source_type=SourceType.WELL_KNOWN,
        git_url="",
        git_sha="contenthas",
        skills=("their-skill",),
        agents_installed=("claude-code",),
        installed_at="2026-03-08T00:00:00Z",
        updated_at="2026-03-08T00:00:00Z",
    )
    d = _entry_to_dict(entry)
    restored = _dict_to_entry(d)
    assert restored == entry
```

**Step 2: Verify existing lock serialization handles new SourceType values**

The existing `_dict_to_entry` uses `SourceType(d["source_type"])` which should work if the enum has the new values (added in Task 6). Verify tests pass:

```bash
python -m pytest tests/test_lock.py -v
```

If `_dict_to_entry` needs updating (e.g., it uses a hardcoded map), update it to handle all SourceType values.

**Step 3: Commit**

```bash
git add cli/src/openforge/lock.py cli/tests/test_lock.py
git commit -m "feat(cli): support non-git source types in lock file"
```

---

### Task 16: Manual E2E — Thread 2 verification

**Owner:** team-lead (with both agents)

**Step 1: Test local path install**

```bash
cd /tmp && mkdir test-project && cd test-project
openforge add "/Users/jeremy.brown/PERSONAL Files/Documents/20-29 Personal/compass/cc-marketplace"
openforge list
```

Expected: plugins/skills installed from local path.

**Step 2: Test branch ref**

```bash
openforge add <owner>/cc-marketplace#main
openforge list
```

Expected: cloned from specific branch.

**Step 3: Test check → update flow**

```bash
openforge check
# If any are outdated:
openforge update --yes
openforge check  # should now show "all up to date"
```

**Step 4: Test GitLab URL (if accessible)**

```bash
openforge add gitlab:some-org/some-repo  # or https://gitlab.com/...
```

**Step 5: Commit any fixes, then push**

```bash
git push
```

---

## Thread 3: "CLI can discover plugins from the Forge"

### Task 17: CLI — Add ForgeProvider

**Owner:** cli-dev

**Files:**
- Create: `cli/src/openforge/providers/forge.py`
- Create: `cli/tests/test_providers_forge.py`
- Modify: `cli/src/openforge/add.py` (add to `_PROVIDERS`)

**Step 1: Write tests**

```python
# tests/test_providers_forge.py
from unittest.mock import patch
import json
from openforge.providers.forge import ForgeProvider, search_forge
from openforge.types import Source, SourceType

MOCK_MARKETPLACE = {
    "version": "0.1.0",
    "packages": [
        {"name": "security-scanner", "description": "Scan for vulnerabilities", "source": {"type": "url", "url": "https://github.com/acme/security"}},
        {"name": "code-review", "description": "AI code review", "source": {"type": "url", "url": "https://github.com/acme/review"}},
    ],
}

@patch("openforge.providers.forge._http_get")
def test_search_forge(mock_get):
    mock_get.return_value = json.dumps(MOCK_MARKETPLACE)
    results = search_forge("security", forge_url="https://forge.example.com")
    assert len(results) == 1
    assert results[0]["name"] == "security-scanner"

@patch("openforge.providers.forge._http_get")
def test_search_forge_no_results(mock_get):
    mock_get.return_value = json.dumps(MOCK_MARKETPLACE)
    results = search_forge("nonexistent", forge_url="https://forge.example.com")
    assert len(results) == 0

def test_forge_provider_matches():
    p = ForgeProvider()
    s = Source(source_type=SourceType.FORGE, url="my-plugin")
    assert p.matches(s) is True
```

**Step 2: Implement ForgeProvider**

```python
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen, Request

from openforge.config_file import get_config
from openforge.providers.base import FetchResult
from openforge.types import Source, SourceType

def _http_get(url: str) -> str:
    req = Request(url, headers={"User-Agent": "openforge-cli"})  # noqa: S310
    with urlopen(req, timeout=30) as resp:  # noqa: S310
        return resp.read(5_000_000).decode()

def search_forge(query: str, forge_url: str | None = None) -> list[dict[str, object]]:
    """Search the Forge marketplace for plugins matching query."""
    config = get_config()
    url = forge_url or config.forge_url
    raw = _http_get(f"{url}/api/marketplace.json")
    marketplace = json.loads(raw)
    packages = marketplace.get("packages", [])
    query_lower = query.lower()
    return [
        p for p in packages
        if query_lower in p.get("name", "").lower()
        or query_lower in p.get("description", "").lower()
        or any(query_lower in t.lower() for t in p.get("tags", []))
    ]

class ForgeProvider:
    def matches(self, source: Source) -> bool:
        return source.source_type == SourceType.FORGE

    def fetch(self, source: Source, dest: Path) -> FetchResult:
        """Look up plugin in Forge, then delegate to git clone."""
        config = get_config()
        raw = _http_get(f"{config.forge_url}/api/marketplace.json")
        marketplace = json.loads(raw)
        packages = marketplace.get("packages", [])

        plugin_name = source.url  # forge:plugin-name → url = "plugin-name"
        match = next((p for p in packages if p.get("name") == plugin_name), None)
        if not match:
            msg = f"plugin '{plugin_name}' not found in Forge"
            raise ValueError(msg)

        # Extract git URL from source field and delegate to GitProvider
        pkg_source = match.get("source", {})
        git_url = pkg_source.get("url", "")
        if not git_url:
            msg = f"plugin '{plugin_name}' has no source URL"
            raise ValueError(msg)

        from openforge.providers.git import GitProvider
        git_source = Source(source_type=SourceType.GITHUB, url=git_url)
        return GitProvider().fetch(git_source, dest)
```

**Step 3: Add to providers in add.py**

```python
from openforge.providers.forge import ForgeProvider
_PROVIDERS = [GitProvider(), LocalProvider(), WellKnownProvider(), ForgeProvider()]
```

**Step 4: Run tests and pyright**

```bash
python -m pytest tests/test_providers_forge.py -v
python -m pytest --tb=short
pyright
```

**Step 5: Commit**

```bash
git add cli/src/openforge/providers/forge.py cli/tests/test_providers_forge.py cli/src/openforge/add.py
git commit -m "feat(cli): add ForgeProvider for Forge-based plugin discovery and install"
```

---

### Task 18: CLI — Add remote `find` capability

**Owner:** cli-dev

**Files:**
- Modify: `cli/src/openforge/find_cmd.py`
- Modify: `cli/tests/test_find.py`

**Step 1: Write tests for remote and combined find**

```python
# Add to tests/test_find.py
from unittest.mock import patch

@patch("openforge.find_cmd.search_forge")
def test_find_remote(mock_search, capsys):
    mock_search.return_value = [
        {"name": "security-scanner", "description": "Scan vulns", "tags": ["security"]},
    ]
    find_command(query="security", is_global=False, remote=True)
    captured = capsys.readouterr()
    assert "security-scanner" in captured.out

@patch("openforge.find_cmd.search_forge")
def test_find_remote_no_results(mock_search, capsys):
    mock_search.return_value = []
    find_command(query="nonexistent", is_global=False, remote=True)
    captured = capsys.readouterr()
    assert "no plugins found" in captured.out.lower()
```

**Step 2: Update find_cmd.py**

Add `--remote` and `--all` flags:

```python
def find_command(
    query: str = typer.Argument(..., help="Search query"),
    is_global: bool = typer.Option(False, "--global", "-g", help="Search globally installed"),
    remote: bool = typer.Option(False, "--remote", "-r", help="Search the Forge catalogue"),
    all_sources: bool = typer.Option(False, "--all", help="Search both local and remote"),
) -> None:
    """Search for plugins and skills."""
    show_local = not remote or all_sources
    show_remote = remote or all_sources

    if show_local:
        # existing local search logic
        ...

    if show_remote:
        from openforge.providers.forge import search_forge
        try:
            results = search_forge(query)
        except Exception as exc:
            _console.print(f"[yellow]Forge search failed: {exc}[/yellow]")
            results = []

        if results:
            table = Table(title="Forge Results")
            table.add_column("Name")
            table.add_column("Description")
            table.add_column("Install")
            for r in results:
                name = r.get("name", "")
                table.add_row(name, r.get("description", ""), f"openforge add forge:{name}")
            _console.print(table)
        elif show_remote and not show_local:
            _console.print("[yellow]No plugins found on the Forge.[/yellow]")

    send_event("find", {"query": query, "remote": show_remote, "results_count": len(results) if show_remote else 0})
```

**Step 3: Run tests and pyright**

```bash
python -m pytest tests/test_find.py -v
python -m pytest --tb=short
pyright
```

**Step 4: Commit**

```bash
git add cli/src/openforge/find_cmd.py cli/tests/test_find.py
git commit -m "feat(cli): add remote find via Forge API (--remote, --all flags)"
```

---

### Task 19: Manual E2E — Thread 3 verification

**Owner:** team-lead (with both agents)

**Step 1: Ensure Forge is running with seeded data**

```bash
cd forge && bun run dev
```

**Step 2: Test remote find**

```bash
cd /tmp/test-project
openforge find <known-plugin-name> --remote
```

Expected: table showing matching plugins from the Forge with install commands.

**Step 3: Test combined find**

```bash
openforge find <query> --all
```

Expected: both local and remote results displayed.

**Step 4: Test forge: prefix install**

```bash
openforge add forge:<plugin-name>
openforge list
```

Expected: plugin installed from Forge lookup → git clone.

**Step 5: Commit any fixes, final push**

```bash
git push
```

---

## Summary

| Thread | Tasks | Owner split |
|--------|-------|------------|
| Thread 1: Webhook + Check | Tasks 1-8 | forge-dev: 1-5, cli-dev: 6-7, both: 8 |
| Thread 2: Update + Sources | Tasks 9-16 | cli-dev: 9-15, both: 16 |
| Thread 3: Remote Find | Tasks 17-19 | cli-dev: 17-18, both: 19 |

**Total:** 19 tasks, 3 end-to-end verification gates.

**Parallel opportunities within Thread 1:** Tasks 1-5 (Forge) and Tasks 6-7 (CLI) can run simultaneously. Task 8 (E2E) requires both.
