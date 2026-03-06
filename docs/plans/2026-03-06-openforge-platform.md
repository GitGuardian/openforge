# OpenForge — Product Requirements Document

**Version:** 0.2
**Date:** 2026-03-06
**Author:** Jeremy Brown + Claude
**Status:** Active

---

## 1. Overview

OpenForge is an open-source platform for distributing, discovering, and curating AI agent plugins and skills. It consists of **the Forge** (a web app) and a **CLI tool** that work together to let teams manage a trusted internal catalogue of plugins, with community features (voting, discussion, install tracking) layered on top of git-backed storage.

The canonical plugin format is Claude Code's `.claude-plugin/` structure. The CLI is a drop-in superset of skills.sh — same source syntax, same file layout on disk, same agent support (51 agents) — plus full plugin support (MCP config, commands, hooks). It adapts plugins for installation across all major AI agents.

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
                    - Internal plugin monorepo
                    - External blessed repos (anthropics/claude-plugins-official, etc.)
                         |
                         | webhook on push
                         v
              +---------------------+
              |  The Forge (Web App)|   Bun + Hono + HTMX + Drizzle
              |                     |   Hosted on Railway + Supabase
              |   - Browse/search   |   Auth: Supabase Auth
              |   - Vote/discuss    |   Modes: public or private
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
                    Supabase (Postgres + Auth)
                    - Plugin metadata (indexed from git)
                    - Votes, comments, tags
                    - Install events (telemetry) + OTel emission
                    - User accounts (Supabase Auth), ownership, roles
                    - Registry of registered git sources
                    - Row Level Security on all tables

              +---------------------+
              |   CLI (Python)      |   Distributed via uvx / PyPI
              |                     |   Package name: openforge
              |   - add/remove      |   Drop-in superset of skills.sh
              |   - find/list       |   51 agent support
              |   - check/update    |   Config: .openforge.toml /
              |   - config          |     ~/.config/openforge/config.toml
              |   - Multi-agent     |
              |     adaptation      |
              +---------------------+

              +---------------------+
              |  Claude Code/Cowork |   Native marketplace support
              |  (direct)           |   marketplace add <forge-url>
              |                     |   Post-install hook for telemetry
              +---------------------+

              +---------------------+
              |  skills.sh (compat) |   .well-known/skills/index.json
              |  npx skills add     |   Compatible file layout on disk
              +---------------------+
```

### 5.2 Storage model

**Git repos** are the source of truth for plugin/skill content. The Forge never stores plugin files in the database.

**Supabase/Postgres** is the source of truth for community data: votes, comments, install events, user accounts, ownership, approval status, registry of git sources. Row Level Security is enabled on all tables from day one.

**Webhook-driven indexing:** When a git repo is pushed, a webhook fires and the Forge re-indexes plugin metadata (names, descriptions, versions, SKILL.md frontmatter) into Postgres. The Forge reads from its own DB for browsing and search; git remains canonical for content.

### 5.3 Multiple registries

The Forge maintains a list of registered git sources:

| Registry | Type | Example |
|----------|------|---------|
| Internal monorepo | Primary | `github.com/acme-corp/agent-plugins` |
| Anthropic official | Blessed external | `github.com/anthropics/claude-plugins-official` |
| Anthropic knowledge-work | Blessed external | `github.com/anthropics/knowledge-work-plugins` |
| Team-specific repos | Internal | `github.com/acme-corp/team-x-plugins` |
| Other blessed repos | External | Admin-approved third-party repos |

Registries are managed by admin users via the Forge UI. Each registered repo must contain a `marketplace.json` or discoverable SKILL.md files.

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

The CLI supports all 51 agents from skills.sh via a data-driven agent registry. Each agent has a name, skills directory, global skills directory, detection function, and a set of capabilities.

Plugins are stored at `.agents/plugins/<name>/`, standalone skills at `.agents/skills/<name>/`. Skills from plugins are symlinked to all detected agents' skills directories universally. Richer plugin components (MCP, commands, hooks) are installed only to agents that support them.

**Capabilities per agent (Phase 1):**

| Agent | Capabilities |
|-------|-------------|
| Claude Code/Cowork | `skills`, `mcp`, `commands`, `hooks`, `agents`, `env` |
| Cursor | `skills`, `mcp`, `commands` |
| All other 49 agents | `skills` |

Adding capabilities to an agent is a one-line config change. Implementing a new capability means writing the adapter for that agent's format.

**Installation strategy:**
- Default: symlink from agent skills dir → canonical location
- Fallback: copy if symlinks not supported (e.g. Windows without dev mode)
- Compatible file layout with skills.sh — both tools put skills in `.agents/skills/`

---

## 6. Features

### 6.1 The Forge — Browse and discover

- **Catalogue page:** List all plugins and skills across all registered repos, with name, description, category, tags, install count, vote score.
- **Search:** Full-text search across plugin names, descriptions, skill content, and tags.
- **Filters:** By category, tag, source repo, agent compatibility, approval status.
- **Detail page:** Per plugin/skill — full description, README, list of contained skills/commands/agents, install instructions, version history.
- **Marketplace.json endpoint:** `GET /api/marketplace.json` — serves a dynamic `marketplace.json` that Claude Code/Cowork can consume directly via `claude plugin marketplace add <forge-url>`.
- **Well-known endpoint:** `GET /.well-known/skills/index.json` — compatible with skills.sh CLI and the well-known provider protocol.

### 6.2 The Forge — Community features

- **Upvote/downvote:** Reddit-style per plugin/skill. One vote per user per item. Net score displayed.
- **Threaded comments:** Per plugin/skill. Supports replies (nested one level). Markdown formatting.
- **Install count:** Displayed per plugin/skill, fed by CLI telemetry and post-install hooks.
- **Composite ranking:** Configurable formula combining install count, vote score, and recency.

### 6.3 The Forge — Curation and approval

- **Submission review queue:** New plugins submitted via ZIP upload enter "pending review" state.
- **Curator dashboard:** Curators see pending submissions, can approve, request changes, or reject.
- **Approval model:** First submission requires curator review. After approval, the plugin owner can push updates freely (CI checks run automatically, users notified via email).
- **Deprecation:** Curators or owners can mark plugins as deprecated (hidden from default browse, warning on install).
- **Notification:** Slack + email notifications to curators on new submissions, to owners on approval/rejection, to users on plugin updates.

### 6.4 The Forge — Non-technical plugin submission

**Upload flow:**

1. User clicks "Submit a plugin" and uploads a ZIP file.
2. The Forge extracts and validates:
   - Has `.claude-plugin/plugin.json`?
   - Has at least one `SKILL.md` with valid frontmatter?
   - No secrets detected (integrate with ggshield or similar scanning).
   - Claude Code LLM-based security scan for prompt injection and other risks.
3. The Forge shows a preview: "Found 1 plugin with 3 skills and 1 MCP server."
4. User edits metadata in a form: display name, description, category, tags, README.
5. User submits for review.
6. The Forge backend:
   - Assigns version `0.1.0` (first submission).
   - Creates branch `submissions/<username>/<plugin-name>` in the internal monorepo.
   - Commits plugin files to `plugins/<name>/`.
   - Updates `marketplace.json` (adds entry).
   - Opens MR on GitHub with auto-generated title and description.
   - Marks as "pending review" in the Forge DB.
   - Notifies curators via Slack + email.

**Update flow:**

1. Owner clicks "Update" on their plugin and uploads a new ZIP.
2. The Forge diffs against current version and shows changes.
3. Auto-increments version (minor for new skills/commands, patch for content changes; owner can override).
4. Prompts for changelog note (optional).
5. Commits directly to main branch (owner has publish rights post-approval).
6. CI runs security checks.
7. On CI pass: the Forge re-indexes, users notified of update via email.
8. On CI fail: owner notified, changes held until fixed.

### 6.5 The Forge — Admin

- **Registry management:** Add/remove registered git sources. Configure webhook URLs.
- **Allowed email domains:** Admins configure an allowlist of email domains (e.g. `acme.com`, `contractor.acme.com`) that can register. Sign-up attempts from unlisted domains are rejected. If the allowlist is empty, registration is open to all.
- **User roles:** Admin (manage registries, curators, settings, allowed domains), Curator (approve/reject submissions), Owner (manage own plugins), User (browse, vote, comment, install).
- **Plugin ownership:** Track owners and editors per plugin. Owners can add/remove editors.

### 6.6 CLI — Core commands

```bash
# Add a plugin or skill (auto-detects type, adapts per agent)
uvx openforge add <owner/repo>              # all skills/plugins from repo
uvx openforge add <owner/repo>@<skill>      # specific skill from repo
uvx openforge add <owner/repo> --agent cursor  # target specific agent
uvx openforge add <owner/repo> --global     # install globally

# Search/browse
uvx openforge find [query]                  # local in Phase 1, remote in Phase 2
uvx openforge find --tag security

# List installed plugins and skills
uvx openforge list
uvx openforge list --global
uvx openforge list --agent claude-code

# Remove a plugin or skill
uvx openforge remove <name>
uvx openforge remove <name> --global

# Check for updates
uvx openforge check

# Update all plugins and skills
uvx openforge update

# Configure CLI
uvx openforge config set forge.url https://forge.acme.com
uvx openforge config get forge.url
uvx openforge config list

# Initialise a new plugin from template (Phase 2+)
uvx openforge init <plugin-name>
```

Source syntax is drop-in compatible with skills.sh (`owner/repo`, `owner/repo@skill`, full URLs).

### 6.7 CLI — Installation behaviour

1. Parse source and fetch content from git repo (Phase 1) or the Forge API (Phase 2).
2. Auto-detect content type: plugin (has `.claude-plugin/plugin.json`) or standalone skills.
3. Store canonical copy: plugins at `.agents/plugins/<name>/`, standalone skills at `.agents/skills/<name>/`.
4. Detect installed agents (all 51 supported agents checked).
5. Per agent, based on capabilities:
   - Symlink skills to agent's skills directory (all agents).
   - Generate MCP config in agent-specific format (agents with `mcp` capability).
   - Translate commands to agent format (agents with `commands` capability).
   - Install hooks (agents with `hooks` capability).
   - Skip unsupported components with a note.
6. Write to `.openforge-lock.json`.
7. Report telemetry to the Forge (fire-and-forget, respects `DO_NOT_TRACK=1`).
8. Print summary of what was installed where.

### 6.8 CLI — Telemetry

- **Protocol:** Simple JSON POST to the Forge. The Forge stores events in Postgres and emits OTel spans/events server-side (companies can route to their own OTel collector).
- **Events:** add, remove, find, check, update.
- **Data per event:** Plugin/skill name, version, source, source type, target agents, CLI version, CI detection. When authenticated to a company Forge, includes user identity.
- **Privacy:** Disabled via `DO_NOT_TRACK=1`. Fire-and-forget (never blocks CLI). No PII in anonymous mode. Auto-disabled in CI. Skips telemetry for private repos.
- **Default endpoint:** `openforge.gitguardian.com/api/telemetry` (configurable via `.openforge.toml` or `~/.config/openforge/config.toml`).

### 6.9 Install tracking — Post-install hooks

Every plugin published through the Forge includes a bundled `SessionStart` hook that pings the Forge on first activation per version:

```bash
#!/bin/sh
FLAG="$HOME/.cache/openforge/activated-<plugin>-<version>"
[ -f "$FLAG" ] && exit 0
curl -s -X POST https://<forge>/api/telemetry/activate \
  -d '{"plugin":"<name>","version":"<version>"}' > /dev/null 2>&1 || true
mkdir -p "$(dirname "$FLAG")" && touch "$FLAG"
```

This captures installs via `claude plugin install` (native CLI) and Cowork desktop installs that bypass the OpenForge CLI.

### 6.10 Claude Code/Cowork native integration

- The Forge serves a `marketplace.json` at a stable URL.
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
- The Forge-served marketplace.json logs access for discovery tracking.

---

## 7. Data model (Postgres/Supabase)

### Core tables

```sql
-- Allowed email domains for registration
create table allowed_domains (
  id uuid primary key default gen_random_uuid(),
  domain text not null unique,            -- "acme.com"
  created_at timestamptz default now()
);

-- Registered git sources
create table registries (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,              -- "internal-plugins", "anthropic-official"
  git_url text not null,                  -- "https://github.com/acme-corp/agent-plugins.git"
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

-- User accounts (managed by Supabase Auth)
create table users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  display_name text,
  role text default 'user',               -- admin, curator, user
  auth_id uuid unique,                    -- from Supabase Auth (auth.users.id)
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
2. **Secret scanning:** Run ggshield (or equivalent) to detect leaked credentials.
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
| The Forge server | Bun + Hono |
| The Forge UI | HTMX + Tailwind CSS (CDN) |
| The Forge DB | Supabase (Postgres + RLS) + Drizzle ORM |
| The Forge hosting | Railway (behind Cloudflare) |
| The Forge auth | Supabase Auth (email/password, magic link, OAuth providers) |
| CLI | Python 3.10+ with Typer |
| CLI distribution | PyPI (`openforge`), installed via `uvx openforge` |
| CLI config | `.openforge.toml` (project) + `~/.config/openforge/config.toml` (user) |
| Telemetry | JSON POST to Forge, Forge emits OTel server-side |
| Plugin storage | Git repos (GitHub) |
| Git operations | GitHub API (webhooks, branch/MR creation) |
| Secret scanning | ggshield integration |
| Security scanning | Claude Code LLM review |
| Notifications | Slack app + transactional email |

---

## 11. Repo structure

Single repo: `github.com/<org>/openforge`

```
openforge/
  cli/                          # Python CLI (uvx openforge)
    pyproject.toml              # Package: openforge
    src/
      openforge/
        __init__.py
        cli.py                  # Typer app, entry point
        add.py                  # add command
        remove.py               # remove command
        find.py                 # find command (local search)
        list.py                 # list command
        config.py               # config command
        agents/
          registry.py           # All 51 agent configs (data-driven)
          base.py               # AgentConfig dataclass + AgentAdapter protocol
          adapters/
            claude.py           # Claude Code MCP/commands/hooks adapter
            cursor.py           # Cursor MCP/commands adapter
        providers/
          base.py               # Provider protocol
          github.py             # GitHub clone + content detection
          registry.py           # Forge API provider (Phase 2)
          wellknown.py          # Well-known URL provider (Phase 2)
          source_parser.py      # Parse owner/repo@skill syntax
        installer.py            # Core install logic (symlink/copy, agent dispatch)
        plugins.py              # plugin.json / marketplace.json parsing
        skills.py               # SKILL.md parsing
        lock.py                 # Lock file management (.openforge-lock.json)
        config_file.py          # TOML config file read/write/precedence
        telemetry.py            # Fire-and-forget JSON POST
        types.py
    tests/
  forge/                        # The Forge (web app)
    package.json
    tsconfig.json
    drizzle.config.ts
    Dockerfile
    .env.example
    src/
      index.ts                  # Hono app entry
      types.ts                  # Shared Hono types (AppEnv)
      routes/
        pages.ts                # HTML pages (browse, detail, submit, admin)
        api.ts                  # JSON API (marketplace.json, telemetry, well-known)
        health.ts               # GET /health
      db/
        schema.ts               # Drizzle schema (with RLS)
        index.ts                # DB client
      lib/
        git.ts                  # GitHub API operations (indexing, MR creation)
        validation.ts           # Plugin/skill validation
        notifications.ts        # Slack + email
        supabase.ts             # Supabase client (auth, storage)
      views/
        layout.ts               # HTML layout (Tailwind + HTMX)
      middleware/
        auth.ts                 # Supabase Auth middleware
    drizzle/                    # Migrations
    public/                     # Static files
  docs/
    plans/                      # PRDs and design docs
    architecture.md
    deployment.md
    contributing.md
  .openforge.toml               # Project-level CLI config (optional)
  .mcp.json                     # MCP servers (Railway, Supabase, Context7)
  CLAUDE.md                     # Agent instructions
  README.md
  LICENSE                       # Apache 2.0
```

---

## 12. Rollout plan

### Phase 0: Name reservation
- Register `openforge` on PyPI (placeholder package).
- Register `openforge` on npm (placeholder package).
- Create GitHub repo for OpenForge.

### Phase 1: CLI (MVP)
- Core commands: `add`, `remove`, `find`, `list`, `config`.
- All 51 agents supported for skills; Claude Code + Cursor for plugin extras.
- Install from git repos (GitHub shorthand, URLs) — drop-in compatible with skills.sh syntax.
- Basic telemetry (JSON POST, fire-and-forget).
- Publish to PyPI.

### Phase 2: The Forge (MVP)
- Browse/search plugins indexed from registered git repos.
- Upvote/downvote and threaded comments.
- Serve `marketplace.json` and `.well-known/skills/index.json`.
- Supabase Auth (email/password, magic link, optional OAuth) with allowed email domains.
- Row Level Security on all tables.
- Public and private deployment modes.
- Webhook-driven indexing from GitHub.
- Deploy to Railway + Supabase (first instance: `openforge.gitguardian.com`, private mode).

### Phase 3: Non-technical submissions
- ZIP upload flow with validation.
- Auto-MR creation on GitHub.
- Curator review dashboard.
- Notification system (Slack + email).

### Phase 4: Polish and expand
- Install tracking via post-install hooks.
- Additional agent capabilities beyond skills (MCP, commands for more agents).
- CI pipeline for plugin security scanning (ggshield, LLM prompt injection review).
- Plugin update flow with versioning (`check`, `update` commands).
- Admin panel for registry management.
- Penetration testing with internal security tools.

### Phase 5: Open-source release
- Clean up for public consumption.
- Generic Postgres support (no Supabase dependency).
- Documentation for self-hosting.
- Announce.

---

## 13. Open items

| Item | Notes |
|------|-------|
| Public domain | TBD — for the public/open community Forge instance. Internal is `openforge.gitguardian.com`. |
| Claude Code security scan | Define the prompt/criteria for LLM-based plugin review |
| Forge design | Wireframes/mockups needed before Phase 2 implementation |
| CLI auth | Does the CLI need to authenticate with the Forge? (For anonymous telemetry: no. For company instance with user tracking: yes.) |
