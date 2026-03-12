# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from openforge.lock import write_lock
from openforge.types import ContentType, LockEntry, LockFile, SourceType

runner = CliRunner()


def _make_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    write_lock(
        lock_path,
        LockFile(
            entries={
                "lint": LockEntry(
                    type=ContentType.SKILL,
                    source="acme/tools@lint",
                    source_type=SourceType.GITHUB,
                    git_url="https://github.com/acme/tools",
                    git_sha="abc123",
                    skills=("lint",),
                    agents_installed=("claude-code",),
                    installed_at="2026-03-06T12:00:00Z",
                    updated_at="2026-03-06T12:00:00Z",
                ),
                "format": LockEntry(
                    type=ContentType.SKILL,
                    source="acme/tools@format",
                    source_type=SourceType.GITHUB,
                    git_url="https://github.com/acme/tools",
                    git_sha="abc123",
                    skills=("format",),
                    agents_installed=("claude-code",),
                    installed_at="2026-03-06T12:00:00Z",
                    updated_at="2026-03-06T12:00:00Z",
                ),
            }
        ),
    )


def _build_app() -> typer.Typer:
    """Build a multi-command test app so typer uses subcommand routing."""
    from openforge.find_cmd import find_command

    test_app = typer.Typer()
    test_app.command("find")(find_command)

    @test_app.command("noop")
    def _noop() -> None:
        """Placeholder to force multi-command mode."""

    _ = _noop  # suppress reportUnusedFunction

    return test_app


def test_find_by_name(tmp_path: Path) -> None:
    test_app = _build_app()
    _make_lock(tmp_path)

    with patch("openforge.find_cmd.get_project_dir", return_value=tmp_path):
        result = runner.invoke(test_app, ["find", "lint"])
        assert result.exit_code == 0
        assert "lint" in result.output


def test_find_by_skill_name(tmp_path: Path) -> None:
    """find should match against skill names, not just entry names."""
    test_app = _build_app()
    _make_lock(tmp_path)

    with patch("openforge.find_cmd.get_project_dir", return_value=tmp_path):
        result = runner.invoke(test_app, ["find", "format"])
        assert result.exit_code == 0
        assert "format" in result.output


def test_find_no_results(tmp_path: Path) -> None:
    test_app = _build_app()

    with patch("openforge.find_cmd.get_project_dir", return_value=tmp_path):
        result = runner.invoke(test_app, ["find", "nonexistent"])
        assert result.exit_code == 0
        assert "No results found." in result.output


# --- Phase 4: Remote find ---


def test_find_remote(tmp_path: Path) -> None:
    """--remote searches the Forge and displays results."""
    test_app = _build_app()

    with (
        patch("openforge.find_cmd.get_project_dir", return_value=tmp_path),
        patch("openforge.find_cmd.search_forge") as mock_search,
    ):
        mock_search.return_value = [
            {"name": "security-scanner", "description": "Scan vulns", "tags": ["security"]},
        ]
        result = runner.invoke(test_app, ["find", "security", "--remote"])
        assert result.exit_code == 0
        assert "security-scanner" in result.output
        assert "forge:security-scanner" in result.output


def test_find_remote_no_results(tmp_path: Path) -> None:
    """--remote with no matches shows a message."""
    test_app = _build_app()

    with (
        patch("openforge.find_cmd.get_project_dir", return_value=tmp_path),
        patch("openforge.find_cmd.search_forge") as mock_search,
    ):
        mock_search.return_value = []
        result = runner.invoke(test_app, ["find", "nonexistent", "--remote"])
        assert result.exit_code == 0
        assert "no" in result.output.lower()


def test_find_all_combines_local_and_remote(tmp_path: Path) -> None:
    """--all shows both local and remote results."""
    test_app = _build_app()
    _make_lock(tmp_path)

    with (
        patch("openforge.find_cmd.get_project_dir", return_value=tmp_path),
        patch("openforge.find_cmd.search_forge") as mock_search,
    ):
        mock_search.return_value = [
            {"name": "remote-lint", "description": "Remote linter", "tags": []},
        ]
        result = runner.invoke(test_app, ["find", "lint", "--all"])
        assert result.exit_code == 0
        # Local result
        assert "lint" in result.output
        # Remote result
        assert "remote-lint" in result.output


def test_find_remote_error_handled(tmp_path: Path) -> None:
    """If Forge search fails, show a warning instead of crashing."""
    test_app = _build_app()

    with (
        patch("openforge.find_cmd.get_project_dir", return_value=tmp_path),
        patch("openforge.find_cmd.search_forge", side_effect=Exception("connection refused")),
    ):
        result = runner.invoke(test_app, ["find", "anything", "--remote"])
        assert result.exit_code == 0
        assert "failed" in result.output.lower() or "error" in result.output.lower()
