from __future__ import annotations

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
