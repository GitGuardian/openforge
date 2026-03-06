from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

import typer

from openforge.types import Source, DetectedContent, ContentType, SkillInfo


def _fake_content_root(source: Source, dest: Path) -> Path:
    return dest


def test_add_skill_from_github(tmp_path: Path) -> None:
    """Integration test: add a skill, verify it prints success."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.add.detect_agents", return_value=[]), \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        # Mock: GitHub provider fetches to a temp dir with a skill
        def fake_fetch(source: Source, dest: Path) -> str:
            skill_dir = dest / "skills" / "lint"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: lint\n---\n")
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        # Mock: content detection finds the skill
        mock_content.return_value = DetectedContent(
            content_type=ContentType.SKILL,
            skills=(SkillInfo(name="lint", path="skills/lint"),),
        )

        result = runner.invoke(test_app, ["acme/tools"])
        assert result.exit_code == 0, result.output
        assert "lint" in result.output


def test_add_with_specific_agent(tmp_path: Path) -> None:
    """Test --agent flag."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.add.install_to_all_agents", return_value=["cursor"]), \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        def fake_fetch(source: Source, dest: Path) -> str:
            skill_dir = dest / "skills" / "lint"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: lint\n---\n")
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        mock_content.return_value = DetectedContent(
            content_type=ContentType.SKILL,
            skills=(SkillInfo(name="lint", path="skills/lint"),),
        )

        result = runner.invoke(test_app, ["acme/tools", "--agent", "cursor"])
        assert result.exit_code == 0, result.output


def test_e2e_with_local_repo(tmp_path: Path, sample_skill_repo: Path) -> None:
    """Full flow: detect content, create canonical storage, write lock file."""
    from openforge.plugins import detect_content
    from openforge.installer import create_canonical_storage
    from openforge.lock import add_lock_entry, read_lock
    from openforge.types import LockEntry, SourceType

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    content = detect_content(sample_skill_repo)
    assert len(content.skills) == 3

    for skill in content.skills:
        source_dir = sample_skill_repo / "skills" / skill.name
        create_canonical_storage(
            source_dir=source_dir,
            project_dir=project_dir,
            name=skill.name,
            content_type=content.content_type,
            is_global=False,
        )

    # Verify canonical storage
    for name in ["lint", "format", "test"]:
        assert (project_dir / ".agents" / "skills" / name / "SKILL.md").exists()

    # Write and verify lock file
    lock_path = project_dir / ".openforge-lock.json"
    for skill in content.skills:
        add_lock_entry(lock_path, skill.name, LockEntry(
            type=content.content_type,
            source="acme/tools",
            source_type=SourceType.GITHUB,
            git_url="https://github.com/acme/tools",
            git_sha="abc123",
            skills=[skill.name],
            agents_installed=[],
            installed_at="2026-03-06T12:00:00Z",
            updated_at="2026-03-06T12:00:00Z",
        ))

    lock = read_lock(lock_path)
    assert len(lock.entries) == 3


def test_add_symlinks_point_to_canonical_not_temp(tmp_path: Path) -> None:
    """After add, agent symlinks must point to .agents/skills/, not to temp dir."""
    from openforge.add import add_command
    from openforge.agents.base import AgentConfig

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    fake_agent = AgentConfig(
        name="test-agent",
        display_name="Test Agent",
        skills_dir=str(tmp_path / ".test-agent" / "skills"),
        global_skills_dir=None,
        detect=lambda: True,
        capabilities=frozenset({"skills"}),
    )

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.installer.detect_agents", return_value=[fake_agent]), \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        def fake_fetch(source: Source, dest: Path) -> str:
            skill_dir = dest / "skills" / "lint"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: lint\n---\n")
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        mock_content.return_value = DetectedContent(
            content_type=ContentType.SKILL,
            skills=(SkillInfo(name="lint", path="skills/lint"),),
        )

        result = runner.invoke(test_app, ["acme/tools"])
        assert result.exit_code == 0, result.output

    # The symlink in the agent dir must point to the canonical location
    agent_link = tmp_path / ".test-agent" / "skills" / "lint"
    assert agent_link.is_symlink()
    target = agent_link.resolve()
    canonical = tmp_path / ".agents" / "skills" / "lint"
    assert target == canonical.resolve(), f"Symlink points to {target}, expected {canonical.resolve()}"


def test_add_shows_friendly_error_on_clone_failure(tmp_path: Path) -> None:
    """When git clone fails (repo not found), show a friendly error, not a traceback."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        MockProvider.return_value.fetch.side_effect = subprocess.CalledProcessError(
            128, ["git", "clone"], stderr="fatal: repository not found"
        )

        result = runner.invoke(test_app, ["acme/nonexistent"])
        # Should NOT show a Python traceback
        assert "Traceback" not in result.output
        # Should show a user-friendly error message
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert "failed" in output_lower or "error" in output_lower or "could not" in output_lower
