# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from openforge.lock import write_lock
from openforge.types import ContentType, LockEntry, LockFile, SourceType

runner = CliRunner()


def _make_app() -> typer.Typer:
    """Build a multi-command Typer app so that sub-command routing is active."""
    from openforge.list_cmd import list_command

    app = typer.Typer()
    app.command("list")(list_command)

    @app.command("noop")
    def _noop() -> None:  # pragma: no cover  # pyright: ignore[reportUnusedFunction]
        """Dummy command to enable sub-command routing."""

    return app


def _make_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    write_lock(lock_path, LockFile(entries={
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
    }))


def test_list_shows_installed(tmp_path: Path) -> None:
    test_app = _make_app()
    _make_lock(tmp_path)

    with patch("openforge.list_cmd.get_project_dir", return_value=tmp_path):
        result = runner.invoke(test_app, ["list"])
        assert result.exit_code == 0
        assert "lint" in result.output
        assert "acme/tools" in result.output


def test_list_empty(tmp_path: Path) -> None:
    test_app = _make_app()

    with patch("openforge.list_cmd.get_project_dir", return_value=tmp_path):
        result = runner.invoke(test_app, ["list"])
        assert result.exit_code == 0
        assert "No plugins or skills installed." in result.output


def test_list_with_agent_filter(tmp_path: Path) -> None:
    """List with --agent filters to entries installed for that agent."""
    test_app = _make_app()
    _make_lock(tmp_path)

    with patch("openforge.list_cmd.get_project_dir", return_value=tmp_path):
        result = runner.invoke(test_app, ["list", "--agent", "claude-code"])
        assert result.exit_code == 0
        assert "lint" in result.output


def test_list_with_agent_filter_no_match(tmp_path: Path) -> None:
    """List with --agent for a non-matching agent shows appropriate message."""
    test_app = _make_app()
    _make_lock(tmp_path)

    with patch("openforge.list_cmd.get_project_dir", return_value=tmp_path):
        result = runner.invoke(test_app, ["list", "--agent", "cursor"])
        assert result.exit_code == 0
        assert "No plugins or skills installed for agent 'cursor'." in result.output
