# Phase 1: CLI MVP — Design

## Overview

Phase 1 delivers a standalone CLI (`uvx openforge`) that installs plugins and skills from GitHub repos across all detected AI agents. No Forge (web app) integration — pure git-based installation. This makes the CLI useful from day one.

The CLI is a drop-in superset of skills.sh: same source syntax, same file layout on disk, same agent support — plus full plugin support (MCP config, commands, hooks).

## Scope

**In scope:**
- Commands: `add`, `remove`, `list`, `find` (local), `config`
- Provider: GitHub only (owner/repo shorthand, full URLs)
- Agent support: all 51 agents for skills, Claude Code + Cursor for plugin extras
- Auto-detection of plugin vs standalone skill repos
- Lock file management (`.openforge-lock.json`)
- Config file support (`.openforge.toml`, `~/.config/openforge/config.toml`)
- Basic telemetry (fire-and-forget, anonymous, to default endpoint)
- Rich terminal output (tables, progress bars, colour-coded summaries)

**Out of scope (Phase 2+):**
- Forge integration (registry provider, voting, comments)
- Well-known provider
- `check`, `update`, `init` commands
- Post-install hooks
- ZIP upload / submission flow

## Command Interface

```bash
# Add a plugin or skill from GitHub
uvx openforge add owner/repo                    # all skills/plugins from repo
uvx openforge add owner/repo@skill-name         # specific skill
uvx openforge add owner/repo --agent cursor     # target specific agent
uvx openforge add owner/repo --global           # install globally

# Remove a plugin or skill
uvx openforge remove plugin-name
uvx openforge remove plugin-name --global

# List installed plugins and skills
uvx openforge list
uvx openforge list --global
uvx openforge list --agent claude-code

# Search locally installed skills
uvx openforge find [query]
uvx openforge find --tag security

# Configure CLI
uvx openforge config set forge.url https://forge.acme.com
uvx openforge config get forge.url
uvx openforge config list
```

Matches skills.sh command names exactly: `add`, `remove`, `list`, `find`. Someone migrating from `npx skills` to `uvx openforge` just swaps the command prefix.

## Source Parsing

The CLI accepts the same source formats as skills.sh:

| Input | Parsed as |
|-------|-----------|
| `owner/repo` | GitHub repo, all skills/plugins |
| `owner/repo@skill-name` | GitHub repo, specific skill |
| `owner/repo/path/to/subdir` | GitHub repo, subdirectory |
| `https://github.com/owner/repo` | Full GitHub URL |
| `https://github.com/owner/repo/tree/main/skills/foo` | Specific path in repo |

Auth: uses `GITHUB_TOKEN` or `GH_TOKEN` env var for private repos. No auth needed for public repos.

## Content Detection

After cloning/fetching a repo, the CLI determines what it contains:

**Plugin detection:**
- Has `.claude-plugin/plugin.json` → single plugin
- Has `marketplace.json` → multi-plugin repo, parse manifest for plugin list

**Skill detection** (when no plugin manifest found):
- Root `SKILL.md`
- `skills/` directory
- `skills/.curated/`, `skills/.experimental/`, `skills/.system/`
- Agent-specific dirs (`.claude/skills/`, `.agents/skills/`)
- Recursive search as fallback

Same priority order as skills.sh.

If `@skill-name` is specified, filter results to the matching skill only — regardless of whether it lives inside a plugin or standalone.

## Installation

### Canonical storage

```
.agents/
  plugins/
    my-plugin/                    # full plugin (has .claude-plugin/)
      .claude-plugin/plugin.json
      skills/
        skill-a/SKILL.md
        skill-b/SKILL.md
      commands/
      hooks/
      .mcp.json
  skills/
    standalone-skill/             # standalone skill (just SKILL.md)
      SKILL.md
```

Plugins go to `.agents/plugins/<name>/`, standalone skills go to `.agents/skills/<name>/`.

### Agent installation

On `openforge add`, the CLI:

1. Detects which agents are installed (run each agent's `detect()`)
2. If `--agent` flag is set, target only that agent
3. For each detected agent, install based on its capabilities

**What gets installed per capability:**

| Capability | Action |
|-----------|--------|
| `skills` | Symlink each skill dir to agent's skills dir |
| `mcp` | Read `.mcp.json`, generate agent-specific MCP config |
| `commands` | Read `commands/*.md`, translate to agent format |
| `hooks` | Copy `hooks/hooks.json` to agent hooks location |
| `agents` | Copy `agents/*.md` to agent definitions location |
| `env` | Print required env vars with setup instructions |

**Symlink strategy:**
- Default: symlink from agent skills dir → canonical location
- Fallback: copy if symlinks not supported
- Example: `.claude/skills/skill-a/` → `../../.agents/plugins/my-plugin/skills/skill-a/`

All 51 agents get skills via symlink. Only Claude Code and Cursor get richer plugin components in Phase 1. Adding capabilities to other agents is a one-line config change.

### Global installs

When `--global` is set:
- Plugins stored in `~/.config/openforge/plugins/<name>/`
- Skills stored in `~/.config/openforge/skills/<name>/`
- Symlinks point to each agent's global skills dir (e.g. `~/.claude/skills/`)
- Lock file at `~/.config/openforge/lock.json`

## Agent Registry

Data-driven — all 51 agents defined as config entries in a single module:

```python
@dataclass(frozen=True)
class AgentConfig:
    name: str                              # "claude-code"
    display_name: str                      # "Claude Code"
    skills_dir: str                        # ".claude/skills"
    global_skills_dir: str | None          # "~/.claude/skills"
    detect: Callable[[], bool]             # check if installed
    capabilities: frozenset[str]           # {"skills", "mcp", ...}
    show_in_list: bool = True
```

Phase 1 capabilities:

| Agent | Capabilities |
|-------|-------------|
| Claude Code | `skills`, `mcp`, `commands`, `hooks`, `agents`, `env` |
| Cursor | `skills`, `mcp`, `commands` |
| All other 49 agents | `skills` |

Extending an agent's capabilities is adding strings to its `frozenset`. Implementing a new capability for an agent means writing the config generator (e.g. "how to write Codex's MCP config format").

## Lock File

`.openforge-lock.json` at project root (or `~/.config/openforge/lock.json` for global):

```json
{
  "version": 1,
  "entries": {
    "my-plugin": {
      "type": "plugin",
      "source": "owner/repo",
      "source_type": "github",
      "git_url": "https://github.com/owner/repo",
      "git_sha": "abc123",
      "skills": ["skill-a", "skill-b"],
      "agents_installed": ["claude-code", "cursor", "gemini-cli"],
      "installed_at": "2026-03-06T12:00:00Z",
      "updated_at": "2026-03-06T12:00:00Z"
    },
    "standalone-skill": {
      "type": "skill",
      "source": "other/repo@standalone-skill",
      "source_type": "github",
      "git_url": "https://github.com/other/repo",
      "git_sha": "def456",
      "skills": ["standalone-skill"],
      "agents_installed": ["claude-code"],
      "installed_at": "2026-03-06T12:00:00Z",
      "updated_at": "2026-03-06T12:00:00Z"
    }
  }
}
```

Compatible disk layout with skills.sh — both tools put skills in `.agents/skills/`. But separate lock files (we track richer metadata: plugin type, skill membership, agent capabilities used).

## Configuration

Precedence (highest to lowest):

1. Environment variables (`OPENFORGE_FORGE_URL`, `DO_NOT_TRACK`, etc.)
2. `.openforge.toml` (project-level, checked into repo)
3. `~/.config/openforge/config.toml` (user-level, MDM-pushable)
4. Defaults

```toml
# .openforge.toml or ~/.config/openforge/config.toml
[forge]
url = "https://openforge.gitguardian.com"

[telemetry]
enabled = true
```

Config commands:

```bash
uvx openforge config set forge.url https://forge.acme.com   # writes to user config
uvx openforge config get forge.url                           # shows resolved value + source
uvx openforge config list                                    # shows all config with sources
```

## Telemetry

- Simple JSON POST to configured Forge URL (default: `openforge.gitguardian.com/api/telemetry`)
- Fire-and-forget — never blocks CLI
- Disabled via `DO_NOT_TRACK=1`
- Auto-disabled in CI (detect common CI env vars)
- No PII in anonymous mode
- Events: `add`, `remove`, `find`

Payload:

```json
{
  "event": "add",
  "source": "owner/repo",
  "source_type": "github",
  "type": "plugin",
  "skills": ["skill-a", "skill-b"],
  "agents": ["claude-code", "cursor"],
  "cli_version": "0.1.0",
  "ci": false
}
```

## Project Structure

```
cli/
  pyproject.toml
  src/
    openforge/
      __init__.py
      cli.py                    # Typer app — registers all commands
      add.py                    # add command
      remove.py                 # remove command
      list.py                   # list command
      find.py                   # find command (local search)
      config.py                 # config command
      agents/
        __init__.py
        registry.py             # AGENTS list + detect/install logic
        base.py                 # AgentConfig dataclass + AgentAdapter protocol
        adapters/
          __init__.py
          claude.py             # Claude Code MCP/commands/hooks adapter
          cursor.py             # Cursor MCP/commands adapter
      providers/
        __init__.py
        base.py                 # Provider protocol
        github.py               # GitHub clone + content detection
        source_parser.py        # Parse owner/repo@skill syntax
      skills.py                 # SKILL.md parsing (frontmatter extraction)
      plugins.py                # plugin.json / marketplace.json parsing
      installer.py              # Core install logic (symlink/copy, agent dispatch)
      lock.py                   # Lock file read/write
      config_file.py            # TOML config file read/write/precedence
      telemetry.py              # Fire-and-forget HTTP POST
      types.py                  # Shared types (Plugin, Skill, Source, etc.)
  tests/
    __init__.py
    test_add.py
    test_remove.py
    test_list.py
    test_find.py
    test_source_parser.py
    test_installer.py
    test_lock.py
    test_config_file.py
    test_agents.py
    conftest.py                 # Shared fixtures (temp dirs, mock repos)
```

**Changes from initial scaffold:**
- Renamed `install.py` → `add.py`, `sync.py` → split into future `check.py`/`update.py`
- Added `config.py`, `config_file.py`, `plugins.py`, `installer.py`, `source_parser.py`
- Added `agents/registry.py` and `agents/adapters/` for agent-specific logic
- Added test files

## Dependencies

```toml
[project]
dependencies = [
    "typer>=0.15.0",       # CLI framework
    "httpx>=0.28.0",       # HTTP client (telemetry, GitHub API)
    "rich>=13.9.0",        # Terminal formatting
    "pyyaml>=6.0.0",       # SKILL.md frontmatter parsing
    "tomli>=2.0.0",        # Config file parsing (Python <3.11)
    "tomli-w>=1.0.0",      # Config file writing
]

[dependency-groups]
dev = [
    "pyright>=1.1.390",    # Type checking (strict)
    "pytest>=8.3.0",       # Tests
    "pytest-tmp-files>=0.0.2",  # Temp directory fixtures
]
```

## Type Safety

All Python code strictly typed from day one:

- `from __future__ import annotations` in every file
- Full type annotations on every function (parameters + return)
- `dataclass`, `Protocol`, `Enum`, `TypedDict` where appropriate
- No `Any` unless truly unavoidable
- `pyright` in strict mode, enforced in CI

## Testing Strategy

- Unit tests for each module (source parsing, lock file, config, SKILL.md parsing)
- Integration tests for `add`/`remove` using temp directories with mock repo structures
- Agent detection tests using mocked filesystem
- No network calls in tests — mock GitHub API responses
- `conftest.py` provides fixtures for common test scenarios (temp dirs, sample plugins/skills)

## Acceptance Criteria

1. `uvx openforge add owner/repo` installs all skills from a GitHub repo to all detected agents
2. `uvx openforge add owner/repo` detects and installs a full plugin (with MCP, commands) to Claude Code
3. `uvx openforge add owner/repo@skill` installs a specific skill only
4. `uvx openforge remove name` cleanly removes all symlinks and canonical files
5. `uvx openforge list` shows all installed plugins/skills with source, type, and agents
6. `uvx openforge find query` searches locally installed skills by name/description
7. Lock file is written on add, updated on remove
8. Config file precedence works correctly (env > project > user > defaults)
9. Telemetry fires on add/remove/find, respects `DO_NOT_TRACK=1`, auto-disables in CI
10. `pyright --strict` passes with zero errors
11. All tests pass
