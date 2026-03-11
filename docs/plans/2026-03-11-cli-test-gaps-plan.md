# CLI Test Gaps Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all CLI integration and E2E test gaps identified in the testing matrix, and update testing conventions in cli/CLAUDE.md.

**Architecture:** Integration tests use `unittest.mock.patch` (for urllib-based functions) or `respx` (for httpx-based functions). E2E smoke tests run `openforge` as a subprocess with `XDG_CONFIG_HOME` set to a temp dir for token isolation. TDD order: write failing test first, confirm red, fix, confirm green, commit.

**Tech Stack:** Python 3.10+, pytest, respx, httpx, unittest.mock, subprocess, local Supabase (port 54321)

**Key source facts (verified before writing this plan):**
- `search_forge` lives in `openforge.providers.forge` and uses `urllib.request.urlopen` (not httpx) — mock via `patch('openforge.providers.forge._http_get', return_value=json_string)`
- `check_entry_staleness(name: str, entry: LockEntry) -> CheckResult` — two args; `CheckResult` has `.is_outdated`, `.remote_sha`, `.error`; mock via `patch('openforge.check._git_ls_remote', return_value=sha_string)`
- `publish_command` calls `get_auth_token()` then `ForgeClient(token=token).submit(git_url, description)` — `ForgeClient` uses httpx, so respx works; patch path is `openforge.publish.get_auth_token`
- Token path: `platformdirs.user_config_dir("openforge") / "token.json"` — isolated by setting `XDG_CONFIG_HOME` env var in subprocess

**Prerequisites:** `uv sync` completed in `cli/`. For E2E smoke tests: local Supabase running (`supabase start`). All commands run from `cli/`.

---

## Chunk 1: Conventions + Integration Tests

### Task 1: Add testing conventions to cli/CLAUDE.md

**Files:**
- Modify: `cli/CLAUDE.md`

- [ ] **Step 1: Read cli/CLAUDE.md and locate insertion point**

```bash
cat cli/CLAUDE.md
```

Find the `## Rules` section or end of file.

- [ ] **Step 2: Add the testing conventions block**

Add a new `## Testing Conventions` section:

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add cli/CLAUDE.md
git commit -m "docs(cli): add testing conventions — TDD red/green, 4-tier pyramid"
```

---

### Task 2: Integration — find --remote

**Files:**
- Create: `cli/tests/integration/test_find.py`

Note: `search_forge` uses `urllib.request.urlopen` (not httpx), so `respx` cannot intercept it. We mock `openforge.providers.forge._http_get` instead.

- [ ] **Step 1: Read the forge provider to confirm the mock target**

```bash
grep -n "_http_get\|_fetch_marketplace\|search_forge" cli/src/openforge/providers/forge.py | head -15
```

Confirm `_http_get(url: str) -> str` is the function that makes the HTTP call, and that `_fetch_marketplace` calls it.

- [ ] **Step 2: Write the failing test file**

```python
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for find --remote / search_forge.

search_forge uses urllib.request.urlopen (not httpx), so we patch
openforge.providers.forge._http_get to avoid real network calls.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from openforge.providers.forge import search_forge


def _marketplace_json(packages: list[dict]) -> str:
    """Build a fake marketplace.json response string."""
    return json.dumps({"version": "1", "packages": packages})


class TestSearchForge:
    """Test search_forge() with mocked HTTP transport."""

    def test_returns_matching_results(self) -> None:
        """search_forge filters packages by name match."""
        packages = [
            {"name": "my-plugin", "description": "does things", "skills": []},
            {"name": "other-tool", "description": "unrelated", "skills": []},
        ]
        with patch(
            "openforge.providers.forge._http_get",
            return_value=_marketplace_json(packages),
        ):
            results = search_forge("my-plugin", forge_url="http://fake-forge.local")

        assert len(results) == 1
        assert results[0]["name"] == "my-plugin"

    def test_returns_description_match(self) -> None:
        """search_forge also matches on description field."""
        packages = [
            {"name": "plugin-a", "description": "advanced search helper", "skills": []},
            {"name": "plugin-b", "description": "unrelated", "skills": []},
        ]
        with patch(
            "openforge.providers.forge._http_get",
            return_value=_marketplace_json(packages),
        ):
            results = search_forge("search helper", forge_url="http://fake-forge.local")

        assert any(r["name"] == "plugin-a" for r in results)

    def test_returns_empty_list_on_no_match(self) -> None:
        """search_forge returns [] when no packages match."""
        packages = [{"name": "unrelated", "description": "nothing here", "skills": []}]
        with patch(
            "openforge.providers.forge._http_get",
            return_value=_marketplace_json(packages),
        ):
            results = search_forge("zzz_no_match_zzz", forge_url="http://fake-forge.local")

        assert results == []

    def test_returns_empty_list_for_empty_marketplace(self) -> None:
        """search_forge returns [] when marketplace has no packages."""
        with patch(
            "openforge.providers.forge._http_get",
            return_value=_marketplace_json([]),
        ):
            results = search_forge("anything", forge_url="http://fake-forge.local")

        assert results == []
```

- [ ] **Step 3: Run to verify failing (red)**

```bash
uv run pytest tests/integration/test_find.py -v
```

Expected: FAIL because the file doesn't exist yet. After creation, it should fail with ImportError or a logic error on first pass.

- [ ] **Step 4: Run to confirm passing (green)**

```bash
uv run pytest tests/integration/test_find.py -v
```

Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add cli/tests/integration/test_find.py
git commit -m "test(cli): add integration tests for find --remote (search_forge)"
```

---

### Task 3: Integration — check staleness detection

**Files:**
- Create: `cli/tests/integration/test_check.py`

Note: `check_entry_staleness` is tested here via patching `openforge.check._git_ls_remote`. We construct real `LockEntry` instances (not dicts). Results are accessed via `.is_outdated`, `.remote_sha`, `.error` attributes.

- [ ] **Step 1: Read the LockEntry dataclass fields**

```bash
grep -n "class LockEntry\|source_type\|git_sha\|git_url\|source:" cli/src/openforge/types.py | head -15
```

Confirm the LockEntry field names used in the test below are correct.

- [ ] **Step 2: Write the failing test file**

```python
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for check command — staleness detection.

Tests check_entry_staleness() by patching openforge.check._git_ls_remote.
Uses real LockEntry instances (not dicts) as required by the type signature.
Results are accessed via attributes: .is_outdated, .remote_sha, .error.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from openforge.check import check_entry_staleness
from openforge.types import LockEntry, SourceType


def _make_entry(
    source: str = "https://github.com/owner/repo",
    source_type: SourceType = SourceType.GITHUB,
    git_sha: str = "abc123",
    git_url: str = "https://github.com/owner/repo",
) -> LockEntry:
    """Build a minimal LockEntry for testing. All required fields must be provided."""
    from openforge.types import ContentType
    return LockEntry(
        type=ContentType.SKILL,  # required field — use a valid enum value
        source=source,
        source_type=source_type,
        git_url=git_url,
        git_sha=git_sha,
        skills=(),
        agents_installed=(),
        installed_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


class TestCheckEntryStaleness:
    """Test check_entry_staleness() — the core staleness logic."""

    def test_entry_is_current_when_sha_matches(self) -> None:
        """Entry is not outdated when installed SHA matches remote SHA."""
        sha = "abc123def456"
        entry = _make_entry(git_sha=sha)

        with patch("openforge.check._git_ls_remote", return_value=sha):
            result = check_entry_staleness("my-plugin", entry)

        assert not result.is_outdated
        assert result.remote_sha == sha

    def test_entry_is_outdated_when_sha_differs(self) -> None:
        """Entry is outdated when installed SHA differs from remote SHA."""
        installed_sha = "abc123"
        remote_sha = "def456"
        entry = _make_entry(git_sha=installed_sha)

        with patch("openforge.check._git_ls_remote", return_value=remote_sha):
            result = check_entry_staleness("my-plugin", entry)

        assert result.is_outdated
        assert result.remote_sha == remote_sha

    def test_local_source_is_skipped(self) -> None:
        """Local source entries are skipped — no remote to compare."""
        entry = _make_entry(
            source="/Users/someone/local/repo",
            source_type=SourceType.LOCAL,
        )

        result = check_entry_staleness("local-plugin", entry)

        assert not result.is_outdated
        assert result.error is not None
        assert "local" in result.error.lower()
```

- [ ] **Step 3: Run to verify failing (red)**

```bash
uv run pytest tests/integration/test_check.py -v
```

Expected: FAIL. If `_make_entry` uses wrong LockEntry fields, you'll get a TypeError — fix field names using the schema from Step 1.

- [ ] **Step 4: Fix LockEntry construction if field names differ**

Read the full LockEntry dataclass:
```bash
grep -A 20 "class LockEntry" cli/src/openforge/types.py
```

Update `_make_entry` to use the exact field names and types from the dataclass.

- [ ] **Step 5: Run to confirm passing (green)**

```bash
uv run pytest tests/integration/test_check.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add cli/tests/integration/test_check.py
git commit -m "test(cli): add integration tests for check staleness detection"
```

---

### Task 4: Integration — publish via ForgeClient (respx)

**Files:**
- Create: `cli/tests/integration/test_publish.py`

Note: `publish_command` calls `get_auth_token()` then `ForgeClient(token=token).submit()`. `ForgeClient` uses httpx, so respx works. We patch `openforge.publish.get_auth_token` to return a mock token and use `@respx.mock` to intercept the httpx submission call.

`ForgeClient.submit()` is already tested in `test_api_client_transport.py` — this plan adds tests for the `publish_command` flow: auth check, URL validation, and successful end-to-end invocation.

- [ ] **Step 1: Read the conftest for mock_forge_url fixture**

```bash
cat cli/tests/integration/conftest.py
```

Note how `mock_forge_url` is defined and what URL it provides.

- [ ] **Step 2: Check ForgeClient constructor signature**

```bash
grep -n "def __init__\|forge_url\|class ForgeClient" cli/src/openforge/api_client.py | head -10
```

Note whether `ForgeClient` reads `forge_url` from config or accepts it as a constructor arg.

- [ ] **Step 3: Write the failing test file**

```python
# SPDX-License-Identifier: Apache-2.0
"""Integration tests for publish command — ForgeClient.submit() transport layer.

publish_command calls get_auth_token() then ForgeClient(token=token).submit().
ForgeClient uses httpx, so we use respx to intercept requests.
Patch path for auth: openforge.publish.get_auth_token.
"""

from __future__ import annotations

import json
from typing import cast
from unittest.mock import patch

import httpx
import pytest
import respx
from httpx import Response

from openforge.api_client import ForgeClient


class TestPublishIntegration:
    """Test publish flow via ForgeClient at the HTTP transport layer."""

    @respx.mock
    def test_submit_posts_to_submissions_endpoint(
        self, mock_forge_url: str
    ) -> None:
        """submit() POSTs to /api/submissions."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-1", "status": "pending"})
        )

        client = ForgeClient(token="test-token-123", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo")

        assert route.called

    @respx.mock
    def test_submit_sends_description_when_provided(
        self, mock_forge_url: str
    ) -> None:
        """submit() includes description field in body when provided."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-2", "status": "pending"})
        )

        client = ForgeClient(token="tok", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo", "My plugin description")

        request = cast(httpx.Request, route.calls[0].request)  # type: ignore[index]
        body = json.loads(request.content)
        assert body.get("description") == "My plugin description"

    @respx.mock
    def test_submit_omits_description_when_not_provided(
        self, mock_forge_url: str
    ) -> None:
        """submit() without description sends None or omits the field."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-3", "status": "pending"})
        )

        client = ForgeClient(token="tok", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo")

        request = cast(httpx.Request, route.calls[0].request)  # type: ignore[index]
        body = json.loads(request.content)
        # description may be absent or None — either is acceptable
        assert body.get("description") in (None, "")
```

Note: The "publish exits 1 when not logged in" auth-guard test requires running `openforge` as a real subprocess, which belongs in `tests/e2e/` (it uses the `run_openforge` fixture from `tests/e2e/conftest.py`). That test is added in Task 5 as part of the auth smoke suite.

- [ ] **Step 4: Run to verify failing (red)**

```bash
uv run pytest tests/integration/test_publish.py -v
```

Expected: FAIL. If `ForgeClient` doesn't accept `forge_url` as a constructor arg, update tests to patch `openforge.api_client.ForgeClient._base_url` or use the conftest fixture approach from `test_api_client_transport.py`.

- [ ] **Step 5: Fix constructor call if needed**

```bash
grep -n "def __init__\|self._base_url\|forge_url" cli/src/openforge/api_client.py | head -15
```

Update `ForgeClient(token=..., forge_url=...)` to match the actual constructor.

- [ ] **Step 6: Run to confirm passing (green)**

```bash
uv run pytest tests/integration/test_publish.py -v
```

Expected: all 3 tests pass.

- [ ] **Step 7: Commit**

```bash
git add cli/tests/integration/test_publish.py
git commit -m "test(cli): add integration tests for publish command (ForgeClient transport)"
```

---

## Chunk 2: CLI E2E Smoke Tests

### Task 5: E2E smoke — auth login, logout, status

**Files:**
- Create: `cli/tests/e2e/test_auth_smoke.py`

**Token isolation strategy:** `platformdirs.user_config_dir("openforge")` respects the `XDG_CONFIG_HOME` env var on Linux/Mac. Setting `XDG_CONFIG_HOME=/tmp/some-dir` in subprocess env makes the CLI write `token.json` to `/tmp/some-dir/openforge/token.json` instead of `~/.config/openforge/token.json`.

**Prerequisite:** Local Supabase must be running (`supabase start`).

- [ ] **Step 1: Verify XDG_CONFIG_HOME isolation works**

```bash
XDG_CONFIG_HOME=/tmp/xdg-test uv run python -c "from platformdirs import user_config_dir; print(user_config_dir('openforge'))"
```

Expected output: `/tmp/xdg-test/openforge`

If this doesn't work (e.g. macOS uses different platform dirs), use `APPDATA` on Windows or check `platformdirs` behaviour:
```bash
uv run python -c "import platformdirs; help(platformdirs.user_config_dir)"
```

Note the correct env var for your platform before writing the test.

- [ ] **Step 2: Get the Supabase anon key from forge/.env**

```bash
grep SUPABASE_ANON_KEY forge/.env 2>/dev/null || grep SUPABASE_ANON_KEY .env 2>/dev/null || echo "Check supabase status for key"
supabase status 2>/dev/null | grep anon
```

Note the anon key — needed for creating the test user via Supabase API.

- [ ] **Step 3: Write the failing test file**

```python
# SPDX-License-Identifier: Apache-2.0
"""E2E smoke tests for auth commands — login, logout, status.

Token isolation: XDG_CONFIG_HOME is set to a temp dir per test so the CLI
writes token.json there instead of ~/.config/openforge/token.json.

Requires: local Supabase running (supabase start from repo root).
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import pytest

SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://127.0.0.1:54321")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
CLI_DIR = Path(__file__).parent.parent.parent  # cli/


def _create_supabase_user(email: str, password: str) -> None:
    """Create a test user via Supabase Auth REST API."""
    res = httpx.post(
        f"{SUPABASE_URL}/auth/v1/signup",
        json={"email": email, "password": password},
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        timeout=10,
    )
    if res.status_code not in (200, 201):
        pytest.skip(f"Could not create Supabase test user (is Supabase running?): {res.text}")


def _run_cli(
    args: list[str],
    xdg_config_home: str,
    stdin: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run openforge CLI as a subprocess with isolated config dir."""
    env = {
        **os.environ,
        "XDG_CONFIG_HOME": xdg_config_home,
        "OPENFORGE_SUPABASE_URL": SUPABASE_URL,
    }
    return subprocess.run(
        ["uv", "run", "openforge", *args],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=CLI_DIR,
        env=env,
        timeout=30,
    )


@pytest.mark.skipif(
    not SUPABASE_ANON_KEY,
    reason="SUPABASE_ANON_KEY not set — is local Supabase running?",
)
class TestAuthSmoke:
    """Subprocess smoke tests for auth login / logout / status."""

    def test_auth_login_stores_token(self, tmp_path: Path) -> None:
        """openforge auth login stores token.json with 0o600 permissions."""
        email = f"auth-smoke-{int(time.time())}@test.local"
        password = "smoke-test-pass-123!"
        _create_supabase_user(email, password)

        xdg = str(tmp_path / "xdg")
        result = _run_cli(["auth", "login"], xdg, stdin=f"{email}\n{password}\n")

        assert result.returncode == 0, (
            f"auth login failed\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        token_file = Path(xdg) / "openforge" / "token.json"
        assert token_file.exists(), "token.json was not created after login"

        mode = oct(token_file.stat().st_mode)[-3:]
        assert mode == "600", f"token.json permissions {mode} — expected 600"

        data = json.loads(token_file.read_text())
        assert "access_token" in data
        assert data.get("email") == email

    def test_auth_status_shows_logged_in(self, tmp_path: Path) -> None:
        """openforge auth status shows email after login."""
        email = f"auth-status-{int(time.time())}@test.local"
        password = "smoke-test-pass-123!"
        _create_supabase_user(email, password)

        xdg = str(tmp_path / "xdg")
        _run_cli(["auth", "login"], xdg, stdin=f"{email}\n{password}\n")

        result = _run_cli(["auth", "status"], xdg)

        assert result.returncode == 0
        output = result.stdout + result.stderr
        assert email in output or "logged in" in output.lower()

    def test_auth_logout_removes_token(self, tmp_path: Path) -> None:
        """openforge auth logout deletes token.json."""
        email = f"auth-logout-{int(time.time())}@test.local"
        password = "smoke-test-pass-123!"
        _create_supabase_user(email, password)

        xdg = str(tmp_path / "xdg")
        _run_cli(["auth", "login"], xdg, stdin=f"{email}\n{password}\n")

        token_file = Path(xdg) / "openforge" / "token.json"
        assert token_file.exists(), "token.json should exist after login"

        result = _run_cli(["auth", "logout"], xdg)

        assert result.returncode == 0
        assert not token_file.exists(), "token.json should be deleted after logout"

    def test_publish_exits_1_when_not_logged_in(self, tmp_path: Path) -> None:
        """openforge publish exits with code 1 when no token is stored."""
        xdg = str(tmp_path / "xdg-noauth")
        result = _run_cli(["publish", "https://github.com/owner/repo"], xdg)
        assert result.returncode == 1
        output = result.stdout + result.stderr
        assert "login" in output.lower(), f"Expected 'login' hint in output, got: {output}"
```

- [ ] **Step 4: Run to verify failing (red)**

```bash
uv run pytest tests/e2e/test_auth_smoke.py -v
```

Expected: FAIL. If `XDG_CONFIG_HOME` isolation doesn't work for the `openforge` token path, update `_run_cli` to use the platform-appropriate env var found in Step 1.

- [ ] **Step 5: Diagnose isolation issue if tests fail**

If token is still written to `~/.config/openforge/`:
```bash
# Run python one-liner inside the subprocess env
XDG_CONFIG_HOME=/tmp/xdg-diag uv run python -c \
  "from openforge.auth import _get_token_dir; print(_get_token_dir())"
```

If this prints `/tmp/xdg-diag/openforge`, isolation works. If it prints `~/.config/openforge`, platformdirs is ignoring `XDG_CONFIG_HOME` on this platform — in that case, patch `openforge.auth._get_token_dir` directly using `monkeypatch` in a unit test instead.

- [ ] **Step 6: Run to confirm passing (green)**

```bash
uv run pytest tests/e2e/test_auth_smoke.py -v
```

Expected: all 4 tests pass (3 auth + 1 publish auth-guard; each 3-5s due to Supabase calls).

- [ ] **Step 7: Run full CLI test suite**

```bash
uv run pytest --cov --cov-fail-under=90
```

Expected: 357+ pass (343 + 4 find + 3 check + 3 publish + 4 auth), ≥90% coverage.

- [ ] **Step 8: Commit**

```bash
git add cli/tests/e2e/test_auth_smoke.py
git commit -m "test(cli): add E2E smoke tests for auth login, logout, status"
```

---

## Final Verification

- [ ] **Run full CLI test suite**

```bash
uv run pytest -v 2>&1 | tail -10
```

Expected: 357+ pass, 0 fail.

- [ ] **Run coverage**

```bash
uv run pytest --cov --cov-fail-under=90
```

Expected: ≥90% coverage.

- [ ] **Type check**

```bash
uv run pyright
```

Expected: 0 errors.

- [ ] **Final commit**

```bash
git add cli/tests/integration/test_find.py cli/tests/integration/test_check.py \
  cli/tests/integration/test_publish.py cli/tests/e2e/test_auth_smoke.py cli/CLAUDE.md
git commit -m "test(cli): close integration and E2E test gaps per testing matrix"
```
