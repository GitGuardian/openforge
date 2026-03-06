# OpenForge — Product Requirements Document

**Version:** 0.1 (draft)
**Date:** 2026-03-06
**Author:** Jeremy Brown + Claude
**Status:** Draft — awaiting review

---

## 1. Overview

OpenForge is an open-source platform for distributing, discovering, and curating AI agent plugins and skills. It consists of a **web portal** and a **CLI tool** that work together to let teams manage a trusted internal catalogue of plugins, with community features (voting, discussion, install tracking) layered on top of git-backed storage.

The canonical plugin format is Claude Code's `.claude-plugin/` structure. The CLI adapts plugins for installation across multiple agents (Claude Code, Claude Desktop/Cowork, Cursor, Codex CLI, OpenCode, Gemini CLI, and others).

OpenForge is designed to be generic — any company can self-host and run it.

---

## 2. Problem statement

- **No internal curation layer.** Public directories (skills.sh, LobeHub) index 100k+ skills with no quality gate. Teams need a trusted, curated subset.
- **No community feedback loop.** Existing tools track install counts but have no voting, discussion, or review mechanism.
- **Multi-agent fragmentation.** Engineers use different agents (Claude Code, Cursor, Codex). Installing the same plugin requires manual adaptation per agent.
- **Non-technical users left out.** Claude Desktop/Cowork users who create plugins via "Plugin Create" have no easy way to share them with colleagues.
- **No install visibility.** Native `claude plugin install` and Cowork desktop installs are invisible to the organisation — no telemetry on what's being used.

---

## 3. Goals

1. Provide a trusted, curated internal catalogue of plugins and skills.
2. Enable reddit-style voting and threaded discussion per plugin/skill.
3. Track installs across all agent types (CLI, Claude Code native, Cowork desktop).
4. Support multi-agent installation from a single canonical plugin format.
5. Let non-technical users submit plugins via ZIP upload with guided workflow.
6. Be generic and open-source — any company can self-host with Postgres.

---

## 4. Non-goals (v1)

- Replacing Claude Code's native plugin system — OpenForge complements it.
- Hosting plugin runtime infrastructure (MCP servers, etc.).
- A "Publish to team" skill inside Cowork (future).
- Draft/preview mode for plugin submissions.
- Billing, paid plugins, or a public SaaS offering.

---

## 5. Architecture

### 5.1 High-level components

```
                    Git Repo(s)
                    (source of truth for plugin content)
                    - Internal monorepo (gg-agent-forge on GitHub)
                    - External blessed repos (anthropics/claude-plugins-official, etc.)
                         |
                         | webhook on push
                         v
              +---------------------+
              |   Portal (Web App)  |   Bun + Hono + HTMX + Drizzle
              |                     |   Hosted on Railway
              |   - Browse/search   |   Auth: Okta SSO via Cloudflare
              |   - Vote/discuss    |
              |   - Curate/approve  |
              |   - Upload (ZIP)    |
              |   - Admin panel     |
              |   - Serve           |
              |     marketplace.json|
              |   - Serve           |
              |     .well-known/    |
              |     skills/         |
              +----------+----------+
                         |
                    Supabase (Postgres)
                    - Plugin metadata (indexed from git)
                    - Votes, comments, tags
                    - Install events (telemetry)
                    - User accounts, ownership, roles
                    - Registry of registered git sources

              +---------------------+
              |   CLI (Python)      |   Distributed via uvx / PyPI
              |                     |   Package name: openforge
              |   - install         |
              |   - find/search     |
              |   - list/remove     |
              |   - Multi-agent     |
              |     adaptation      |
              |   - OTel telemetry  |
              +---------------------+

              +---------------------+
              |  Claude Code/Cowork |   Native marketplace support
              |  (direct)           |   marketplace add <portal-url>
              |                     |   Post-install hook for telemetry
              +---------------------+
```

### 5.2 Storage model

**Git repos** are the source of truth for plugin/skill content. The portal never stores plugin files in the database.

**Supabase/Postgres** is the source of truth for community data: votes, comments, install events, user accounts, ownership, approval status, registry of git sources.

**Webhook-driven indexing:** When a git repo is pushed, a webhook fires and the portal re-indexes plugin metadata (names, descriptions, versions, SKILL.md frontmatter) into Postgres. The portal reads from its own DB for browsing and search; git remains canonical for content.

### 5.3 Multiple registries

The portal maintains a list of registered git sources:

| Registry | Type | Example |
|----------|------|---------|
| Internal monorepo | Primary | `github.com/GitGuardian/gg-agent-forge` |
| Anthropic official | Blessed external | `github.com/anthropics/claude-plugins-official` |
| Anthropic knowledge-work | Blessed external | `github.com/anthropics/knowledge-work-plugins` |
| Team-specific repos | Internal | `github.com/GitGuardian/team-x-plugins` |
| Other blessed repos | External | Admin-approved third-party repos |

Registries are managed by admin users via the portal UI. Each registered repo must contain a `marketplace.json` or discoverable SKILL.md files.

### 5.4 Plugin canonical format

Claude Code's `.claude-plugin/` structure:

```
my-plugin/
  .claude-plugin/plugin.json    # Manifest (name, version, description, author, etc.)
  skills/*/SKILL.md             # Agent Skills (universal format)
  commands/*.md                 # Slash commands (Claude Code specific)
  agents/*.md                   # Subagent definitions (Claude Code specific)
  hooks/hooks.json              # Lifecycle hooks
  .mcp.json                     # MCP server configurations
  env.json                      # Required environment variables
  scripts/                      # Utility scripts
  reference/                    # Reference documentation
```

### 5.5 Multi-agent adaptation

The CLI installs the canonical plugin to `.agents/plugins/<name>/` and adapts per detected agent:

| Component | Claude Code/Cowork | Cursor | Codex CLI | OpenCode | Gemini CLI |
|-----------|:------------------:|:------:|:---------:|:--------:|:----------:|
| Skills (SKILL.md) | Symlink | Symlink | Symlink | Symlink | Symlink |
| MCP config | Native | Generate `.cursor/mcp.json` | Generate `.mcp.json` | Generate config | Generate `.gemini/settings.json` |
| Commands | Native | Translate to `.cursor/rules/` MDC | Convert to skill | Convert to `.opencode/agent/` | Inject into GEMINI.md |
| Hooks | Native | Auto-compatible (Cursor reads Claude hooks) | Skip | Skip | Skip |
| Agents | Native | Skip | Skip | Partial translate | Skip |
| env.json | Native | Print setup instructions | Print setup instructions | Print setup instructions | Print setup instructions |

---

## 6. Features

### 6.1 Portal — Browse and discover

- **Catalogue page:** List all plugins and skills across all registered repos, with name, description, category, tags, install count, vote score.
- **Search:** Full-text search across plugin names, descriptions, skill content, and tags.
- **Filters:** By category, tag, source repo, agent compatibility, approval status.
- **Detail page:** Per plugin/skill — full description, README, list of contained skills/commands/agents, install instructions, version history.
- **Marketplace.json endpoint:** `GET /api/marketplace.json` — serves a dynamic `marketplace.json` that Claude Code/Cowork can consume directly via `claude plugin marketplace add <portal-url>`.
- **Well-known endpoint:** `GET /.well-known/skills/index.json` — compatible with skills.sh CLI and the well-known provider protocol.

### 6.2 Portal — Community features

- **Upvote/downvote:** Reddit-style per plugin/skill. One vote per user per item. Net score displayed.
- **Threaded comments:** Per plugin/skill. Supports replies (nested one level). Markdown formatting.
- **Install count:** Displayed per plugin/skill, fed by CLI telemetry and post-install hooks.
- **Composite ranking:** Configurable formula combining install count, vote score, and recency.

### 6.3 Portal — Curation and approval

- **Submission review queue:** New plugins submitted via ZIP upload enter "pending review" state.
- **Curator dashboard:** Curators see pending submissions, can approve, request changes, or reject.
- **Approval model:** First submission requires curator review. After approval, the plugin owner can push updates freely (CI checks run automatically, users notified via email).
- **Deprecation:** Curators or owners can mark plugins as deprecated (hidden from default browse, warning on install).
- **Notification:** Slack + email notifications to curators on new submissions, to owners on approval/rejection, to users on plugin updates.

### 6.4 Portal — Non-technical plugin submission

**Upload flow:**

1. User clicks "Submit a plugin" and uploads a ZIP file.
2. Portal extracts and validates:
   - Has `.claude-plugin/plugin.json`?
   - Has at least one `SKILL.md` with valid frontmatter?
   - No secrets detected (integrate with gg-shield or similar scanning).
   - Claude Code LLM-based security scan for prompt injection and other risks.
3. Portal shows a preview: "Found 1 plugin with 3 skills and 1 MCP server."
4. User edits metadata in a form: display name, description, category, tags, README.
5. User submits for review.
6. Portal backend:
   - Assigns version `0.1.0` (first submission).
   - Creates branch `submissions/<username>/<plugin-name>` in the internal monorepo.
   - Commits plugin files to `plugins/<name>/`.
   - Updates `marketplace.json` (adds entry).
   - Opens MR on GitHub with auto-generated title and description.
   - Marks as "pending review" in portal DB.
   - Notifies curators via Slack + email.

**Update flow:**

1. Owner clicks "Update" on their plugin and uploads a new ZIP.
2. Portal diffs against current version and shows changes.
3. Auto-increments version (minor for new skills/commands, patch for content changes; owner can override).
4. Prompts for changelog note (optional).
5. Commits directly to main branch (owner has publish rights post-approval).
6. CI runs security checks.
7. On CI pass: portal re-indexes, users notified of update via email.
8. On CI fail: owner notified, changes held until fixed.

### 6.5 Portal — Admin

- **Registry management:** Add/remove registered git sources. Configure webhook URLs.
- **User roles:** Admin (manage registries, curators, settings), Curator (approve/reject submissions), Owner (manage own plugins), User (browse, vote, comment, install).
- **Plugin ownership:** Track owners and editors per plugin. Owners can add/remove editors.

### 6.6 CLI — Core commands

```bash
# Install a plugin (auto-detects agents, adapts per agent)
uvx openforge install <plugin-name>
uvx openforge install <plugin-name> --agent cursor  # target specific agent

# Search/browse
uvx openforge find [query]
uvx openforge find --tag security
uvx openforge find --category productivity

# List installed plugins
uvx openforge list

# Remove a plugin
uvx openforge remove <plugin-name>

# Check for updates
uvx openforge check

# Update all plugins
uvx openforge update

# Install from specific registry
uvx openforge install <plugin-name> --registry anthropic-official

# Install a standalone skill (not a full plugin)
uvx openforge add <owner/repo>           # GitHub shorthand
uvx openforge add <owner/repo>@<skill>   # specific skill from repo

# Initialise a new plugin from template
uvx openforge init <plugin-name>
```

### 6.7 CLI — Installation behaviour

1. Fetch plugin from the portal API (discovery) or git repo (content).
2. Store canonical copy at `.agents/plugins/<name>/`.
3. Detect installed agents (check for `.cursor/`, `claude` binary, `.codex/`, etc.).
4. Per agent:
   - Symlink skills to agent-specific directory.
   - Generate MCP config in agent-specific format/location.
   - Translate commands where the target agent supports them.
   - Skip unsupported components with a warning.
5. Report telemetry to the portal (plugin name, version, agents installed for).
6. Print summary of what was installed where.

### 6.8 CLI — Telemetry

- **Protocol:** OpenTelemetry (OTel), similar to skills.sh telemetry model.
- **Events:** install, remove, find, check, update.
- **Data per event:** Plugin name, version, source registry, target agents, CLI version, CI detection.
- **Privacy:** Disabled via `OPENFORGE_DISABLE_TELEMETRY=1` or `DO_NOT_TRACK=1`. Fire-and-forget (never blocks CLI). No PII beyond what's in the event.
- **Endpoint:** Portal API `POST /api/telemetry`.

### 6.9 Install tracking — Post-install hooks

Every plugin published through the portal includes a bundled `SessionStart` hook that pings the portal on first activation per version:

```bash
#!/bin/sh
FLAG="$HOME/.cache/openforge/activated-<plugin>-<version>"
[ -f "$FLAG" ] && exit 0
curl -s -X POST https://<portal>/api/telemetry/activate \
  -d '{"plugin":"<name>","version":"<version>"}' > /dev/null 2>&1 || true
mkdir -p "$(dirname "$FLAG")" && touch "$FLAG"
```

This captures installs via `claude plugin install` (native CLI) and Cowork desktop installs that bypass the OpenForge CLI.

### 6.10 Claude Code/Cowork native integration

- The portal serves a `marketplace.json` at a stable URL.
- Teams add it once: `claude plugin marketplace add https://forge.company.com/api/marketplace.json`
- Or via managed settings in `.claude/settings.json`:
  ```json
  {
    "extraKnownMarketplaces": {
      "openforge": {
        "source": {
          "source": "url",
          "url": "https://forge.company.com/api/marketplace.json"
        }
      }
    }
  }
  ```
- After that, plugins are browsable and installable natively via `/plugin` in Claude Code and "Browse plugins" in Cowork.
- The portal-served marketplace.json logs access for discovery tracking.

---

## 7. Data model (Postgres/Supabase)

### Core tables

```sql
-- Registered git sources
create table registries (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,              -- "gg-agent-forge", "anthropic-official"
  git_url text not null,                  -- "https://github.com/GitGuardian/gg-agent-forge.git"
  registry_type text not null,            -- "internal", "blessed-external"
  webhook_secret text,
  indexed_at timestamptz,
  created_at timestamptz default now()
);

-- Plugins (indexed from git)
create table plugins (
  id uuid primary key default gen_random_uuid(),
  registry_id uuid references registries not null,
  name text not null,
  version text,
  description text,
  category text,
  tags text[],
  readme text,                            -- rendered from plugin README.md
  plugin_json jsonb,                      -- cached plugin.json content
  git_path text,                          -- "plugins/gitlab"
  git_sha text,                           -- commit SHA at index time
  status text default 'approved',         -- approved, pending, deprecated
  install_count int default 0,
  vote_score int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  unique(registry_id, name)
);

-- Skills within plugins (indexed from git)
create table skills (
  id uuid primary key default gen_random_uuid(),
  plugin_id uuid references plugins,      -- null for standalone skills
  registry_id uuid references registries not null,
  name text not null,
  description text,
  skill_md_path text,                     -- "skills/conventions/SKILL.md"
  metadata jsonb,                         -- frontmatter metadata
  created_at timestamptz default now()
);

-- User accounts (linked to SSO)
create table users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  display_name text,
  role text default 'user',               -- admin, curator, user
  sso_subject text unique,                -- from Okta/OIDC
  created_at timestamptz default now()
);

-- Plugin ownership
create table plugin_owners (
  plugin_id uuid references plugins,
  user_id uuid references users,
  role text default 'owner',              -- owner, editor
  primary key (plugin_id, user_id)
);

-- Reddit-style votes
create table votes (
  user_id uuid references users,
  plugin_id uuid references plugins,
  value smallint check (value in (-1, 1)),
  created_at timestamptz default now(),
  primary key (user_id, plugin_id)
);

-- Threaded comments
create table comments (
  id uuid primary key default gen_random_uuid(),
  plugin_id uuid references plugins not null,
  user_id uuid references users not null,
  parent_id uuid references comments,     -- null for top-level, references parent for replies
  body text not null,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Install telemetry events
create table install_events (
  id uuid primary key default gen_random_uuid(),
  plugin_name text not null,
  skill_name text,                        -- null if full plugin install
  version text,
  source text,                            -- "cli", "hook-activate", "marketplace-fetch"
  agents text[],                          -- ["claude-code", "cursor"]
  cli_version text,
  is_ci boolean default false,
  created_at timestamptz default now()
);

-- Plugin submissions (pending review)
create table submissions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users not null,
  plugin_name text not null,
  version text not null,
  status text default 'pending',          -- pending, approved, rejected, changes-requested
  mr_url text,                            -- link to the auto-created MR
  reviewer_notes text,
  submitted_at timestamptz default now(),
  reviewed_at timestamptz
);
```

---

## 8. CI/CD and security

### Plugin validation pipeline

When a plugin is submitted (via ZIP upload or direct MR), CI runs:

1. **Structure validation:** Verify plugin.json schema, SKILL.md frontmatter, required files.
2. **Secret scanning:** Run gg-shield (or equivalent) to detect leaked credentials.
3. **Prompt injection scan:** Use Claude Code to review SKILL.md content, commands, and agent definitions for prompt injection attempts and other LLM-specific security risks.
4. **Linting:** Validate markdown formatting, check for broken internal references.

On the owner's subsequent updates (post-approval):
- Same CI pipeline runs automatically.
- On pass: changes are published, users notified.
- On fail: owner notified, changes held.

---

## 9. Notification system

| Event | Channel | Recipients |
|-------|---------|------------|
| New plugin submission | Slack + email | All curators |
| Submission approved | Email | Plugin owner |
| Submission rejected / changes requested | Email | Plugin owner |
| Plugin updated (by owner) | Email | Users who installed the plugin |
| CI failure on update | Email | Plugin owner |
| Comment on your plugin | Email | Plugin owner + editors |
| Reply to your comment | Email | Comment author |

Slack integration via a Slack app. Email via Supabase Auth emails or a transactional email service (Resend, Postmark, etc.).

---

## 10. Tech stack summary

| Component | Technology |
|-----------|-----------|
| Portal server | Bun + Hono |
| Portal UI | HTMX + Tailwind CSS (CDN) |
| Portal DB | Supabase (Postgres) + Drizzle ORM |
| Portal hosting | Railway |
| Portal auth | Okta SSO via Cloudflare (X-User-Id / X-User-Email headers) |
| CLI | Python 3.10+ with Typer |
| CLI distribution | PyPI (`openforge`), installed via `uvx openforge` |
| CLI telemetry | OpenTelemetry |
| Plugin storage | Git repos (GitHub) |
| Git operations | GitHub API (webhooks, branch/MR creation) |
| Secret scanning | gg-shield integration |
| Security scanning | Claude Code LLM review |
| Notifications | Slack app + transactional email |

---

## 11. Repo structure

Single repo: `github.com/GitGuardian/openforge`

```
openforge/
  cli/                          # Python CLI
    pyproject.toml              # Package: openforge
    src/
      openforge/
        __init__.py
        cli.py                  # Typer app, entry point
        install.py              # Install logic
        find.py                 # Search/browse
        list.py                 # List installed
        remove.py               # Remove
        sync.py                 # Update/check
        agents/                 # Agent detection and adaptation
          claude.py
          cursor.py
          codex.py
          opencode.py
          gemini.py
          base.py               # Agent interface
        providers/              # Source resolution
          github.py
          gitlab.py
          wellknown.py
          registry.py
        skills.py               # SKILL.md parsing
        lock.py                 # Lock file management
        telemetry.py            # OTel integration
        types.py
    tests/
  portal/                       # Web app
    package.json
    src/
      index.ts                  # Hono app entry
      routes/
        pages.ts                # HTML pages (browse, detail, submit, admin)
        api.ts                  # JSON API (marketplace.json, telemetry, well-known)
      db/
        schema.ts               # Drizzle schema
        index.ts                # DB client
      lib/
        git.ts                  # GitHub API operations (indexing, MR creation)
        validation.ts           # Plugin/skill validation
        notifications.ts        # Slack + email
      views/
        layout.ts               # HTML layout
      middleware/
        user.ts                 # SSO user identity
    drizzle/                    # Migrations
  migrations/                   # Shared SQL (if needed outside Drizzle)
  docs/
    architecture.md
    deployment.md
    contributing.md
  README.md
  LICENSE                       # TBD: MIT or Apache 2.0
```

---

## 12. Rollout plan

### Phase 0: Name reservation
- Register `openforge` on PyPI (placeholder package).
- Register `openforge` on npm (placeholder package).
- Confirm GitHub repo: `github.com/GitGuardian/openforge`.

### Phase 1: CLI (MVP)
- Core commands: `install`, `find`, `list`, `remove`.
- Multi-agent adaptation for Claude Code and Cursor.
- Install from git repos (GitHub shorthand, URLs).
- Basic OTel telemetry.
- Publish to PyPI.

### Phase 2: Portal (MVP)
- Browse/search plugins indexed from gg-agent-forge.
- Upvote/downvote and threaded comments.
- Serve `marketplace.json` and `.well-known/skills/index.json`.
- SSO auth via Okta/Cloudflare.
- Webhook-driven indexing from GitHub.
- Deploy to Railway + Supabase.

### Phase 3: Non-technical submissions
- ZIP upload flow with validation.
- Auto-MR creation on GitHub.
- Curator review dashboard.
- Notification system (Slack + email).

### Phase 4: Polish and expand
- Install tracking via post-install hooks.
- Additional agent support (Codex, OpenCode, Gemini).
- CI pipeline for plugin security scanning.
- Plugin update flow with versioning.
- Admin panel for registry management.

### Phase 5: Open-source release
- Clean up for public consumption.
- Generic Postgres support (no Supabase dependency).
- Documentation for self-hosting.
- Choose and apply licence.
- Announce.

---

## 13. Open items

| Item | Notes |
|------|-------|
| Licence | MIT or Apache 2.0 — to be decided |
| Domain | `forge.gitguardian.com`? `openforge.dev`? Internal only initially? |
| gg-agent-forge migration | Move from internal GitLab to GitHub — timing and process |
| Slack app setup | New app or extend existing? |
| Claude Code security scan | Define the prompt/criteria for LLM-based plugin review |
| Portal design | Wireframes/mockups needed before implementation |
| CLI auth | Does the CLI need to authenticate with the portal? (For telemetry: no. For voting/commenting: yes, but that could be portal-only.) |
