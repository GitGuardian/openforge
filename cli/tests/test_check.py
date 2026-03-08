# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from openforge.check import check_command, check_entry_staleness
from openforge.types import ContentType, LockEntry, SourceType

_runner = CliRunner()


def _make_entry(
    git_url: str = "https://github.com/acme/skills",
    git_sha: str = "abc123",
    source_type: SourceType = SourceType.GITHUB,
) -> LockEntry:
    return LockEntry(
        type=ContentType.SKILL,
        source="acme/skills",
        source_type=source_type,
        git_url=git_url,
        git_sha=git_sha,
        skills=("my-skill",),
        agents_installed=("claude-code",),
        installed_at="2026-03-01T00:00:00Z",
        updated_at="2026-03-01T00:00:00Z",
    )


@patch("openforge.check._git_ls_remote", return_value="abc123")
def test_check_entry_up_to_date(mock_ls_remote: object) -> None:
    entry = _make_entry(git_sha="abc123")
    result = check_entry_staleness("acme/skills", entry)
    assert result.is_outdated is False
    assert result.remote_sha == "abc123"


@patch("openforge.check._git_ls_remote", return_value="def456")
def test_check_entry_outdated(mock_ls_remote: object) -> None:
    entry = _make_entry(git_sha="abc123")
    result = check_entry_staleness("acme/skills", entry)
    assert result.is_outdated is True
    assert result.local_sha == "abc123"
    assert result.remote_sha == "def456"


@patch(
    "openforge.check._git_ls_remote",
    side_effect=subprocess.CalledProcessError(128, "git"),
)
def test_check_entry_unreachable(mock_ls_remote: object) -> None:
    entry = _make_entry()
    result = check_entry_staleness("acme/skills", entry)
    assert result.is_outdated is False
    assert result.error is not None


def test_check_entry_local_source() -> None:
    entry = _make_entry(source_type=SourceType.LOCAL)
    result = check_entry_staleness("local-plugin", entry)
    assert result.is_outdated is False
    assert result.error is not None
    assert "local" in result.error.lower()


def test_check_entry_well_known_source() -> None:
    entry = _make_entry(source_type=SourceType.WELL_KNOWN)
    result = check_entry_staleness("wk-plugin", entry)
    assert result.is_outdated is False
    assert result.error is not None


# --- Integration tests for check_command ---


def _write_lock(tmp_path: object, entries: dict[str, LockEntry]) -> None:
    """Write a lock file to a tmp directory for testing."""
    from pathlib import Path

    path = Path(str(tmp_path)) / ".openforge-lock.json"
    payload = {
        "version": 1,
        "entries": {
            name: {
                "type": e.type.value,
                "source": e.source,
                "source_type": e.source_type.value,
                "git_url": e.git_url,
                "git_sha": e.git_sha,
                "skills": list(e.skills),
                "agents_installed": list(e.agents_installed),
                "installed_at": e.installed_at,
                "updated_at": e.updated_at,
            }
            for name, e in entries.items()
        },
    }
    path.write_text(json.dumps(payload))


def test_check_command_empty_lock(tmp_path: object) -> None:
    """check with no installed entries prints a message and exits."""
    from pathlib import Path

    app = typer.Typer()
    app.command()(check_command)

    with patch("openforge.check.get_project_dir", return_value=Path(str(tmp_path))):
        result = _runner.invoke(app, [])
    assert result.exit_code == 0
    assert "no installed" in result.output.lower()


@patch("openforge.check._git_ls_remote", return_value="abc123")
def test_check_command_specific_entry(mock_ls_remote: object, tmp_path: object) -> None:
    """check <name> only checks that entry."""
    from pathlib import Path

    p = Path(str(tmp_path))
    entry = _make_entry(git_sha="abc123")
    _write_lock(p, {"acme/skills": entry, "other/repo": _make_entry(git_sha="xyz")})

    app = typer.Typer()
    app.command()(check_command)

    with (
        patch("openforge.check.get_project_dir", return_value=p),
        patch("openforge.check.send_event"),
    ):
        result = _runner.invoke(app, ["acme/skills"])
    assert result.exit_code == 0
    assert "up to date" in result.output.lower()


def test_check_command_entry_not_found(tmp_path: object) -> None:
    """check <name> with nonexistent entry exits with error."""
    from pathlib import Path

    p = Path(str(tmp_path))
    _write_lock(p, {"acme/skills": _make_entry()})

    app = typer.Typer()
    app.command()(check_command)

    with patch("openforge.check.get_project_dir", return_value=p):
        result = _runner.invoke(app, ["nonexistent"])
    assert result.exit_code == 1
    assert "not found" in result.output.lower()
