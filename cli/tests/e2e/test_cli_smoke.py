# SPDX-License-Identifier: Apache-2.0
"""End-to-end smoke tests — runs openforge as a real subprocess.

These tests verify:
- Entry point resolves and CLI starts
- Help and version output
- Basic commands work as a real binary
- Auth status works without credentials
"""

from __future__ import annotations

from pathlib import Path

from tests.e2e.conftest import RunOpenforge


class TestCLIEntryPoint:
    """Verify the CLI binary starts and responds to basic flags."""

    def test_help_flag(self, run_openforge: RunOpenforge) -> None:
        """openforge --help exits 0 and shows usage."""
        result = run_openforge("--help")
        assert result.returncode == 0
        assert "add" in result.stdout
        assert "remove" in result.stdout
        assert "find" in result.stdout
        assert "list" in result.stdout

    def test_version_flag(self, run_openforge: RunOpenforge) -> None:
        """openforge --version exits 0 and shows version string."""
        result = run_openforge("--version")
        assert result.returncode == 0
        assert "0.1.0" in result.stdout

    def test_short_version_flag(self, run_openforge: RunOpenforge) -> None:
        """-v also shows version."""
        result = run_openforge("-v")
        assert result.returncode == 0
        assert "0.1.0" in result.stdout

    def test_unknown_command_fails(self, run_openforge: RunOpenforge) -> None:
        """An invalid subcommand returns non-zero exit code."""
        result = run_openforge("nonexistent-command")
        assert result.returncode != 0


class TestCLIAuthStatus:
    """Test auth commands without real credentials."""

    def test_auth_status_not_logged_in(self, run_openforge: RunOpenforge) -> None:
        """openforge auth status when not logged in shows appropriate message."""
        result = run_openforge("auth", "status")
        assert result.returncode == 0
        assert "not logged in" in result.stdout.lower()

    def test_auth_help(self, run_openforge: RunOpenforge) -> None:
        """openforge auth --help shows auth subcommands."""
        result = run_openforge("auth", "--help")
        assert result.returncode == 0
        assert "login" in result.stdout
        assert "logout" in result.stdout
        assert "status" in result.stdout


class TestCLIAddLocalRepo:
    """Test add command with a local repo as a real subprocess."""

    def test_add_local_skill_repo(
        self, run_openforge: RunOpenforge, local_skill_repo: Path, tmp_path: Path
    ) -> None:
        """openforge add <local-path> installs skill from local directory."""
        result = run_openforge("add", str(local_skill_repo), cwd=tmp_path)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        assert "test-skill" in result.stdout

    def test_add_then_list(
        self, run_openforge: RunOpenforge, local_skill_repo: Path, tmp_path: Path
    ) -> None:
        """openforge list shows installed entry after add."""
        run_openforge("add", str(local_skill_repo), cwd=tmp_path)
        result = run_openforge("list", cwd=tmp_path)
        assert result.returncode == 0
        # Lock entry key for local repos is the source path
        assert "test-repo" in result.stdout or "Installed" in result.stdout

    def test_add_then_remove(
        self, run_openforge: RunOpenforge, local_skill_repo: Path, tmp_path: Path
    ) -> None:
        """openforge remove removes installed entry by source path."""
        add_result = run_openforge("add", str(local_skill_repo), cwd=tmp_path)
        assert add_result.returncode == 0

        # Remove by source path (local entries are keyed by path)
        result = run_openforge("remove", str(local_skill_repo), cwd=tmp_path)
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestCLIConfigCommand:
    """Test config commands as a real subprocess."""

    def test_config_list(self, run_openforge: RunOpenforge) -> None:
        """openforge config list shows config values."""
        result = run_openforge("config", "list")
        assert result.returncode == 0
        assert "forge.url" in result.stdout

    def test_config_get(self, run_openforge: RunOpenforge) -> None:
        """openforge config get <key> shows a single config value."""
        result = run_openforge("config", "get", "forge.url")
        assert result.returncode == 0
        # Should show the URL value
        assert "openforge" in result.stdout.lower() or "http" in result.stdout.lower()
