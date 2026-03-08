# Phase 4: Automated Indexing & CLI Parity — Design Document

**Date:** 2026-03-08
**Status:** Approved
**Depends on:** Phase 3 (Community Features) — complete
**Goal:** Automate plugin indexing via GitHub webhooks, give the CLI staleness detection and update capabilities, expand source support to match skills.sh, and enable remote plugin discovery from the Forge.

---

## Scope

| In scope | Out of scope (later phases) |
|----------|---------------------------|
| GitHub webhook receiver + HMAC verification | GitLab webhooks (Phase 7) |
| Automated git indexing (refactor seed → library) | Admin UI for registry management (Phase 5+) |
| Schema fixes (skills unique constraint, updated_at, stale detection) | Notification system (Phase 5) |
| CLI `check` command (SHA comparison via `git ls-remote`) | fzf interactive mode (backlog) |
| CLI `update` command (re-fetch + reinstall + show changes) | Search telemetry (backlog) |
| CLI source expansion (GitLab, SSH, local paths, branch refs) | |
| CLI well-known provider (HTTP-based skill discovery) | |
| CLI remote `find` via Forge API | |
| Provider protocol refactor | |

---

## Steel Threads

Phase 4 is delivered as three end-to-end increments (steel threads). Each is usable and testable on its own.

### Thread 1 — "Git push → Forge knows → CLI detects staleness" (skateboard)

- **Forge:** refactor seed into indexing library → webhook endpoint → HMAC verification → schema fixes
- **CLI:** `check` command
- **Done when:** push to test repo → webhook fires → Forge re-indexes → `openforge check` shows "1 outdated"

### Thread 2 — "CLI can update and install from anywhere" (bicycle)

- **CLI:** `update` command → provider protocol refactor → source expansion (GitLab, SSH, local, branch refs) → well-known provider
- **Done when:** `openforge update` pulls latest + `openforge add gitlab:owner/repo`, `openforge add ./local`, `openforge add https://example.com` all work

### Thread 3 — "CLI can discover plugins from the Forge" (car)

- **Forge:** search API endpoint (if needed beyond existing `marketplace.json`)
- **CLI:** remote `find`
- **Done when:** `openforge find security --remote` returns results from the Forge catalogue

---

## Forge: Webhook Receiver

### Endpoint

`POST /api/webhooks/github`

### Flow

```
GitHub push event
  → Verify HMAC-SHA256 signature (X-Hub-Signature-256 header vs registries.webhook_secret)
  → Extract repo URL from payload
  → Match against registries table (by git_url)
  → Return 200 immediately
  → Run indexing in background (Bun async)
```

### Payload Filtering

Only process `push` events to the default branch. Ignore tag pushes, non-default branches, and other event types.

### HMAC Verification

```typescript
const signature = req.headers.get('X-Hub-Signature-256');
const expected = `sha256=${hmac(registry.webhook_secret, rawBody)}`;
if (!timingSafeEqual(signature, expected)) return 401;
```

Using `crypto.timingSafeEqual` to prevent timing attacks.

### Concurrency Guard

Check `registries.indexed_at` timestamp. If indexing started less than 60 seconds ago, skip (return 200 with "indexing already in progress"). No distributed lock needed at our scale.

---

## Forge: Indexing Library Refactor

Extract `seed.ts` logic into `forge/src/lib/indexer.ts`:

```
indexRegistry(registryId: string): Promise<IndexResult>
  → clone repo (shallow, depth 1)
  → scan for plugin.json, marketplace.json, SKILL.md
  → upsert plugins + skills (existing logic)
  → detect stale content (plugins/skills in DB but not in repo → mark status 'removed')
  → update registries.indexed_at
  → cleanup temp dir
  → return { pluginsFound, skillsFound, removed, errors }
```

Seed script becomes a thin wrapper: parse CLI args → find/create registry → call `indexRegistry()`.

### Stale Content Detection

After scanning and upserting, query all plugins/skills for this registry. Any not found in the latest scan get `status = 'removed'`. They remain in the DB (preserving votes/comments) but are hidden from the catalogue by default.

---

## Forge: Schema Changes

| Change | Why |
|--------|-----|
| Add `UNIQUE(registry_id, skill_md_path)` on `skills` | Enable `ON CONFLICT DO UPDATE` like plugins |
| Add `updated_at timestamptz DEFAULT now()` on `skills` | Track content freshness |
| Add `status text DEFAULT 'active'` on `skills` | Support stale content detection ('active', 'removed') |

One new Drizzle migration for these changes.

---

## CLI: `check` Command

```bash
openforge check              # check all installed entries
openforge check <name>       # check a specific entry
```

### Flow

1. Read lock file entries
2. For each entry, run `git ls-remote <git_url> HEAD` (or the specific ref if pinned)
3. Compare remote SHA against lock's `git_sha`
4. Output table: name, status (up to date / outdated), installed SHA (short), remote SHA (short)

Respects `GITHUB_TOKEN`/`GH_TOKEN` for private repos. Runs checks in parallel (asyncio) for speed.

---

## CLI: `update` Command

```bash
openforge update             # update all outdated entries
openforge update <name>      # update a specific entry
openforge update --all       # same as no args, explicit
```

### Flow

1. Run `check` logic to identify outdated entries
2. For each outdated entry: clone new version → detect content → reinstall (same as `add` flow)
3. Show changes summary: new/removed skills, version bump if applicable
4. Update lock entry with new SHA and timestamp
5. Fire telemetry event (event type: `update`)

---

## CLI: Provider Protocol Refactor

Introduce a formal `Provider` protocol in `providers/base.py`:

```python
class Provider(Protocol):
    def match(self, source: str) -> bool: ...
    def resolve(self, source: ParsedSource) -> ResolvedSource: ...
    def fetch(self, resolved: ResolvedSource, dest: Path) -> FetchResult: ...
```

### Implementations

| Provider | Handles | Fetch method |
|----------|---------|-------------|
| `GitProvider` | GitHub, GitLab, SSH, generic git URLs | `git clone` |
| `LocalProvider` | `./path`, `/abs/path` | Validate + use directly (no clone) |
| `WellKnownProvider` | `https://example.com` (non-git URLs) | HTTP fetch `.well-known/skills/index.json` + download files |
| `ForgeProvider` | `forge:name` prefix or `--remote` flag | HTTP fetch from Forge API |

Key insight from skills.sh analysis: GitHub, GitLab, SSH, and generic git all use the same `git clone` — they differ only in URL parsing. One `GitProvider` handles all of them.

---

## CLI: Source Parser Extensions

New source types added to `SourceType` enum:

| Source format | Type | Example |
|--------------|------|---------|
| GitHub shorthand | `GITHUB` | `owner/repo`, `owner/repo@skill` |
| GitHub URL | `GITHUB` | `https://github.com/owner/repo` |
| GitLab URL | `GITLAB` | `https://gitlab.com/owner/repo` |
| GitLab prefix | `GITLAB` | `gitlab:owner/repo` |
| SSH URL | `GIT` | `git@github.com:owner/repo.git` |
| Local path | `LOCAL` | `./my-plugin`, `/abs/path` |
| Branch ref | any | `owner/repo#branch` or `owner/repo@skill#branch` |
| Well-known URL | `WELL_KNOWN` | `https://example.com` |
| Forge name | `FORGE` | `forge:plugin-name` |

Branch refs use `#branch` suffix (consistent with npm-style conventions). Parsed into `ParsedSource.ref` field.

---

## CLI: Well-Known Provider

Different fetch model — no git involved:

1. Fetch `<url>/.well-known/skills/index.json`
2. Validate index structure (array of skills with name, description, files)
3. Download each skill's files via HTTP (SKILL.md required)
4. Install to `.agents/skills/<name>/` (copy, not symlink — no git repo to link to)
5. Lock entry stores source URL instead of git_url, content hash instead of git_sha

---

## CLI: Remote `find`

```bash
openforge find <query>              # searches local (existing behavior)
openforge find <query> --remote     # searches Forge API
openforge find <query> --all        # searches both local and remote
```

Queries `GET /api/marketplace.json` and filters client-side (or a dedicated search endpoint if the Forge adds one). Results show name, description, source, install command.

---

## File Changes

### New Files

**Forge:**

| File | Purpose |
|------|---------|
| `forge/src/lib/indexer.ts` | Reusable indexing library (extracted from seed.ts) |
| `forge/src/routes/webhooks.ts` | GitHub webhook receiver + HMAC verification |

**CLI:**

| File | Purpose |
|------|---------|
| `cli/src/openforge/check.py` | `check` command |
| `cli/src/openforge/update.py` | `update` command |
| `cli/src/openforge/providers/base.py` | `Provider` protocol definition |
| `cli/src/openforge/providers/git.py` | Git provider (GitHub, GitLab, SSH, generic) |
| `cli/src/openforge/providers/local.py` | Local path provider |
| `cli/src/openforge/providers/wellknown.py` | Well-known URL provider |
| `cli/src/openforge/providers/forge.py` | Forge API provider (remote find + add) |

### Modified Files

**Forge:**

| File | Change |
|------|--------|
| `forge/src/index.ts` | Register webhook route |
| `forge/src/scripts/seed.ts` | Refactor to use `indexer.ts` |
| `forge/src/db/schema.ts` | Skills unique constraint, `updated_at`, `status` column |
| New Drizzle migration | Schema changes |

**CLI:**

| File | Change |
|------|--------|
| `cli/src/openforge/cli.py` | Register `check` and `update` commands |
| `cli/src/openforge/providers/source_parser.py` | GitLab, SSH, local, branch ref, well-known, forge parsing |
| `cli/src/openforge/providers/github.py` | Refactor to implement `Provider` protocol (becomes `git.py` or wraps it) |
| `cli/src/openforge/add.py` | Use provider registry instead of hardcoded GitHub |
| `cli/src/openforge/find_cmd.py` | Add `--remote` and `--all` flags |
| `cli/src/openforge/lock.py` | Support well-known entries (content hash instead of git SHA) |
| `cli/src/openforge/types.py` | New `SourceType` variants |

### New Dependencies

**Forge:** None — `crypto` for HMAC is built into Bun/Node.

**CLI:** None expected — `git` is shelled out to (existing pattern), standard library `urllib` for well-known HTTP fetches.

---

## Testing & Verification

### Thread 1: "Git push → Forge knows → CLI detects"

**Forge (manual smoke tests + typecheck):**
- Mock GitHub webhook payload → verify HMAC validation (accept valid, reject invalid/missing)
- Mock webhook → verify `indexRegistry()` runs and upserts plugins/skills
- Mock webhook for repo with removed plugin → verify stale detection marks it 'removed'
- Concurrency guard: two rapid webhook fires → second returns "already indexing"

**CLI (TDD):**
- `check` with all entries up-to-date → shows "all up to date"
- `check` with outdated entry → shows table with SHA diff
- `check` with unreachable remote → graceful error
- `check` with specific name → only checks that entry

**Manual end-to-end (local):**
1. Start local Supabase + Forge
2. Seed from test marketplace repo (`cc-marketplace`)
3. Simulate GitHub webhook (`curl` with HMAC signature)
4. Verify Forge re-indexed
5. Install a plugin via CLI → simulate upstream change → `openforge check` shows outdated

### Thread 2: "Install from anywhere"

**CLI (TDD):**
- Source parser: GitLab URLs (with subgroups, `/-/tree/` paths), SSH URLs, local paths, branch refs (`#branch` suffix), well-known URLs, `forge:` prefix
- `GitProvider.fetch()` with GitLab URL → correct `git clone` invocation
- `LocalProvider.fetch()` → validates path exists, no clone
- `WellKnownProvider.fetch()` → mock HTTP responses, verify index parsing + file download
- `update` with outdated entry → re-fetches, reinstalls, updates lock
- `update` with already up-to-date → skips with message
- `update` showing changes summary → lists new/removed skills
- Provider protocol: all providers implement `match()`, `resolve()`, `fetch()`

**Manual end-to-end (local):**
- `openforge add ./path/to/local/plugin` → installs from local directory
- `openforge add owner/repo#branch` → clones specific branch
- `openforge check` → `openforge update` → verify lock SHA updated

### Thread 3: "Discover from Forge"

**CLI (TDD):**
- `find --remote` with mock Forge API response → displays results
- `find --remote` with no results → "no plugins found"
- `find --remote` with Forge unreachable → graceful error
- `find --all` → merges local + remote results, deduplicates

**Manual end-to-end (local):**
- Start Forge with seeded data
- `openforge find security --remote` → returns matching plugins from Forge
- Copy install command from results → `openforge add` works

### Test Repo

Use `cc-marketplace` (available locally and on GitHub) as the test registry for webhook and indexing tests.

---

## Security Considerations

| Concern | Mitigation |
|---------|-----------|
| Webhook forgery | HMAC-SHA256 signature verification with `timingSafeEqual` |
| Webhook replay | Timestamp check (reject events older than 5 minutes via `X-GitHub-Delivery` dedup) |
| Malicious repo content | Indexer only reads metadata (plugin.json, SKILL.md frontmatter, README) — no code execution |
| Path traversal in git_path | Sanitize plugin/skill paths during indexing (reject `/`, `\`, `..`) |
| Well-known SSRF | Only fetch from user-provided URLs, validate response content-type, size limit on downloads |
| Concurrent indexing race | Timestamp-based guard prevents overlapping index runs |
