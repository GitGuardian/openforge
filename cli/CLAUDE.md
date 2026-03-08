# CLI — Agent Instructions

This file contains rules, commands, and conventions specific to the OpenForge CLI. For project-wide context, see the root `../CLAUDE.md`.

---

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Language | Python 3.10+ | Strictly typed (pyright strict mode). |
| Framework | Typer | CLI framework with auto-generated help. |
| Distribution | PyPI | Installed via `uvx openforge`. |
| Telemetry | JSON POST to the Forge | Fire-and-forget, disabled via `DO_NOT_TRACK=1`. |

---

## Commands

```bash
uv sync                  # Install dependencies
uv run pytest            # Run tests
uv run pyright           # Type check (strict mode)
uv run openforge --help     # Run CLI locally
uv run openforge --version  # Show version
uv run pre-commit run --all-files  # Run all pre-commit hooks
uv run pytest --cov --cov-fail-under=90  # Check coverage
```

---

## Project Structure

```
cli/
  pyproject.toml
  src/
    openforge/
      cli.py                  # Typer app, entry point, --version flag
      add.py                  # add command
      remove.py               # remove command
      find_cmd.py             # find command
      list_cmd.py             # list command
      config.py               # config command
      agents/
        registry.py           # All 75 agent configs (data-driven)
        base.py               # AgentConfig dataclass + AgentAdapter protocol
        adapters/
          claude.py           # Claude Code adapter
          cursor.py           # Cursor adapter
      providers/
        base.py               # Provider protocol
        github.py             # GitHub clone + content detection
        source_parser.py      # Parse owner/repo@skill syntax
      installer.py            # Core install logic (symlink/copy, agent dispatch)
      plugins.py              # plugin.json / marketplace.json parsing
      skills.py               # SKILL.md parsing
      lock.py                 # Lock file (.openforge-lock.json)
      config_file.py          # TOML config read/write/precedence
      telemetry.py            # Fire-and-forget JSON POST
      types.py
  tests/
```

---

## Rules

Follow these strictly. They prevent common failure modes.

**Use Typer for all CLI commands.**
Every command is a Typer command. Use type annotations for arguments and options.

**All Python code must be strictly typed.**
Every function signature must have full type annotations (parameters and return types). Use `dataclass`, `TypedDict`, `Protocol`, and `Enum` where appropriate. No `Any` unless truly unavoidable. Run `pyright` in strict mode — the CI and `pyproject.toml` must enforce this. Prefer `from __future__ import annotations` at the top of every file.

**Agent configs are data-driven.**
All 75 agents are defined as `AgentConfig` entries in `src/openforge/agents/registry.py`. Do not create separate files per agent. Only agents with capabilities beyond `skills` (Claude Code, Cursor) get adapter classes in `agents/adapters/`.

**Telemetry must never block.**
All telemetry calls are fire-and-forget. Never let a telemetry failure prevent a command from completing.

---

## Testing

**Use TDD red/green for all bug fixes.**
When you find a bug or a test fails:
1. **Red**: Write a failing test that reproduces the bug.
2. **Green**: Fix the code to make the test pass.
3. Verify all existing tests still pass (`uv run pytest`).
4. Verify pyright still passes (`uv run pyright src/`).
5. Only then commit the fix.

Never fix a bug without a test that covers it. Never skip the verification step.

**Coverage minimum is 90%.** Enforced by pre-commit hook. Run `uv run pytest --cov --cov-fail-under=90` to check locally.

**Run the full test suite before committing.**
Always run `uv run pytest && uv run pyright src/openforge/` before committing any change.

---

## Key Files

- **`src/openforge/cli.py`** — Typer app. All commands registered here.
- **`src/openforge/agents/base.py`** — AgentConfig dataclass and AgentAdapter protocol.
- **`src/openforge/agents/registry.py`** — All 75 agent definitions.
- **`src/openforge/installer.py`** — Core install logic.

---

## Environment Setup

1. `uv sync`
2. `uv run openforge --help`
