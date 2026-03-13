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
uv run pytest            # Run all tests (unit + integration + e2e)
uv run pytest tests/ --ignore=tests/integration --ignore=tests/e2e  # Run unit tests only (~0.7s)
uv run pytest tests/integration/  # Run respx HTTP transport tests (~1-2s)
uv run pytest tests/e2e/          # Run subprocess smoke tests (~3-5s)
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
      auth.py                 # auth sub-commands (login, logout, status)
      publish.py              # publish command (submit plugin to Forge)
      api_client.py           # ForgeClient — HTTP client for Forge API
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
  tests/                    # Unit tests (mocked, pytest)
    integration/            # respx HTTP transport tests
    e2e/                    # Subprocess smoke tests
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

**Run local CI before pushing anything bigger than a tiny fix.**
```bash
uv run pytest                              # All tests: unit + integration + e2e (~3.5s)
uv run pytest --cov --cov-fail-under=90    # With coverage check
uv run pyright src/openforge/              # Type checking
```
The integration tests (respx) and e2e subprocess tests run without external services. The pre-commit hook already runs all tiers automatically.

**Security patterns (established in Phase 6 hardening):**
- Atomic file writes: use `os.open(O_CREAT|O_WRONLY, 0o600)` + `os.fdopen` + `os.replace` for token/config files
- Path traversal: validate paths stay within expected directories using `resolve().is_relative_to()`
- URL validation: reject non-HTTPS URLs from external sources (marketplace, wellknown)
- Symlink protection: reject symlinks that escape source directories in canonical storage
- Exception narrowing: catch specific exceptions, not bare `except`

---

## Testing Conventions

### Testing pyramid (4 tiers)

| Tier | Name | Tool |
|------|------|------|
| 1 | Unit | `pytest` (mocked) |
| 2 | Integration | `unittest.mock.patch` / `respx` HTTP transport mock |
| 3 | E2E (component) | subprocess smoke tests (`tests/e2e/`) |
| 4 | Cross-component E2E | Playwright + CLI subprocess (in `forge/e2e/cross-component.spec.ts`) |

### Rule: every feature must have

1. A happy-path **integration test** — `patch`/`respx` verifying HTTP calls and logic
2. A happy-path **E2E test** — subprocess smoke test via `run_openforge` fixture
3. Any feature crossing the CLI↔Forge boundary must also have a **cross-component E2E test** coordinated with forge-dev

### TDD order is mandatory

- Write integration and E2E tests **first** (red), then implement until they pass (green)
- When fixing a bug: write a failing test that reproduces the bug first, then fix the code
- Never write implementation code before a failing test exists

### Exceptions (note explicitly — never silently skip)

- Pure config/parsing logic — unit only acceptable
- Features that require external state with no mock path — integration only acceptable

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
