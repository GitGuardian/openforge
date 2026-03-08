# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from openforge.check import CheckResult
from openforge.types import ContentType, LockEntry, LockFile, SourceType
from openforge.update import update_command

_runner = CliRunner()


def _make_entry(
    git_url: str = "https://github.com/acme/skills",
    git_sha: str = "abc123",
) -> LockEntry:
    return LockEntry(
        type=ContentType.SKILL,
        source="acme/skills",
        source_type=SourceType.GITHUB,
        git_url=git_url,
        git_sha=git_sha,
        skills=("my-skill",),
        agents_installed=("claude-code",),
        installed_at="2026-03-01T00:00:00Z",
        updated_at="2026-03-01T00:00:00Z",
    )


@patch("openforge.update.send_event")
@patch("openforge.update.check_entry_staleness")
@patch("openforge.update.read_lock")
@patch("openforge.update.lock_file_path")
@patch("openforge.update.get_project_dir")
def test_update_skips_up_to_date(
    mock_proj: object,
    mock_path: object,
    mock_read: object,
    mock_check: object,
    mock_event: object,
) -> None:
    """Update with no outdated entries prints 'all up to date'."""
    from unittest.mock import MagicMock

    mp = MagicMock()
    mp.return_value = Path("/tmp/test")
    mr = MagicMock()
    mr.return_value = LockFile(entries={"acme/skills": _make_entry()})
    mc = MagicMock()
    mc.return_value = CheckResult(
        name="acme/skills", local_sha="abc", remote_sha="abc", is_outdated=False
    )

    app = typer.Typer()
    app.command()(update_command)

    with (
        patch("openforge.update.get_project_dir", mp),
        patch("openforge.update.lock_file_path", return_value=Path("/tmp/lock.json")),
        patch("openforge.update.read_lock", mr),
        patch("openforge.update.check_entry_staleness", mc),
        patch("openforge.update.send_event"),
    ):
        result = _runner.invoke(app, ["--yes"])
    assert result.exit_code == 0
    assert "up to date" in result.output.lower()


@patch("openforge.update.send_event")
@patch("openforge.update._reinstall_entry")
@patch("openforge.update.check_entry_staleness")
@patch("openforge.update.read_lock")
@patch("openforge.update.lock_file_path")
@patch("openforge.update.get_project_dir")
def test_update_reinstalls_outdated(
    mock_proj: object,
    mock_path: object,
    mock_read: object,
    mock_check: object,
    mock_reinstall: object,
    mock_event: object,
) -> None:
    """Update with outdated entry triggers reinstall."""
    from unittest.mock import MagicMock

    mp = MagicMock()
    mp.return_value = Path("/tmp/test")
    mr = MagicMock()
    mr.return_value = LockFile(entries={"acme/skills": _make_entry()})
    mc = MagicMock()
    mc.return_value = CheckResult(
        name="acme/skills", local_sha="abc", remote_sha="def", is_outdated=True
    )
    mi = MagicMock()
    mi.return_value = None

    app = typer.Typer()
    app.command()(update_command)

    with (
        patch("openforge.update.get_project_dir", mp),
        patch("openforge.update.lock_file_path", return_value=Path("/tmp/lock.json")),
        patch("openforge.update.read_lock", mr),
        patch("openforge.update.check_entry_staleness", mc),
        patch("openforge.update._reinstall_entry", mi),
        patch("openforge.update.send_event"),
    ):
        result = _runner.invoke(app, ["--yes"])
    assert result.exit_code == 0
    mi.assert_called_once()
    assert "updated" in result.output.lower()


def test_update_empty_lock(tmp_path: object) -> None:
    """Update with no installed entries exits cleanly."""
    app = typer.Typer()
    app.command()(update_command)

    with (
        patch("openforge.update.get_project_dir", return_value=Path(str(tmp_path))),
        patch(
            "openforge.update.lock_file_path",
            return_value=Path(str(tmp_path)) / "lock.json",
        ),
    ):
        result = _runner.invoke(app, ["--yes"])
    assert result.exit_code == 0
    assert "no installed" in result.output.lower()
