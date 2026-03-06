from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from openforge.types import LockFile, LockEntry, ContentType, SourceType
from openforge.lock import write_lock

runner = CliRunner()


def test_remove_installed_skill(tmp_path: Path) -> None:
    from openforge.remove import remove_command

    test_app = typer.Typer()
    test_app.command("remove")(remove_command)

    # Setup: create canonical storage + lock entry
    project_dir = tmp_path / "project"
    skill_dir = project_dir / ".agents" / "skills" / "lint"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test")

    lock_path = project_dir / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.SKILL,
        source="acme/tools@lint",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/tools",
        git_sha="abc123",
        skills=["lint"],
        agents_installed=[],
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"lint": entry}))

    with patch("openforge.remove.get_project_dir", return_value=project_dir), \
         patch("openforge.remove.send_event"):
        result = runner.invoke(test_app, ["lint"])
        assert result.exit_code == 0, result.output

    assert not skill_dir.exists()


def test_remove_not_found(tmp_path: Path) -> None:
    from openforge.remove import remove_command

    test_app = typer.Typer()
    test_app.command("remove")(remove_command)

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    with patch("openforge.remove.get_project_dir", return_value=project_dir):
        result = runner.invoke(test_app, ["nonexistent"])
        assert result.exit_code != 0 or "not found" in result.output.lower() or "not installed" in result.output.lower()
