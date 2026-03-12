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


def _supabase_available() -> bool:
    """Check if local Supabase is reachable."""
    try:
        r = httpx.get(f"{SUPABASE_URL}/auth/v1/health", timeout=3)
        return r.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def _create_supabase_user(email: str, password: str) -> None:
    """Create a test user via Supabase Auth REST API."""
    res = httpx.post(
        f"{SUPABASE_URL}/auth/v1/signup",
        json={"email": email, "password": password},
        headers={"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"},
        timeout=10,
    )
    if res.status_code not in (200, 201):
        pytest.skip(f"Could not create Supabase test user: {res.text}")


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
    not _supabase_available() or not SUPABASE_ANON_KEY,
    reason="Local Supabase not running or SUPABASE_ANON_KEY not set",
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
