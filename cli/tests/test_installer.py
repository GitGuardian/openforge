from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from openforge.installer import (
    install_skills_to_agent,
    create_canonical_storage,
    remove_canonical_storage,
)
from openforge.agents.base import AgentConfig
from openforge.types import SkillInfo, ContentType


def _make_agent(tmp_path: Path) -> AgentConfig:
    skills_dir = tmp_path / ".test-agent" / "skills"
    return AgentConfig(
        name="test-agent",
        display_name="Test Agent",
        skills_dir=str(skills_dir),
        global_skills_dir=None,
        detect=lambda: True,
    )


def test_create_canonical_storage_skill(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("---\nname: test\n---\n")

    dest = create_canonical_storage(
        source_dir=source_dir,
        project_dir=tmp_path / "project",
        name="test-skill",
        content_type=ContentType.SKILL,
        is_global=False,
    )
    assert dest.exists()
    assert (dest / "SKILL.md").exists()
    assert "skills" in str(dest)


def test_create_canonical_storage_plugin(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    plugin_dir = source_dir / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"name": "test"}')

    dest = create_canonical_storage(
        source_dir=source_dir,
        project_dir=tmp_path / "project",
        name="test-plugin",
        content_type=ContentType.PLUGIN,
        is_global=False,
    )
    assert dest.exists()
    assert "plugins" in str(dest)


def test_install_skills_to_agent_creates_symlinks(tmp_path: Path) -> None:
    skill_dir = tmp_path / "project" / ".agents" / "skills" / "lint"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: lint\n---\n")

    agent = _make_agent(tmp_path)
    skills = [SkillInfo(name="lint", path=str(skill_dir))]

    install_skills_to_agent(
        agent=agent,
        skills=skills,
        project_dir=tmp_path / "project",
        is_global=False,
    )

    agent_skill = Path(agent.skills_dir) / "lint"
    assert agent_skill.is_symlink()
    assert agent_skill.resolve() == skill_dir.resolve()


def test_remove_canonical_storage(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    skill_dir = project_dir / ".agents" / "skills" / "test"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test")

    remove_canonical_storage(
        project_dir=project_dir,
        name="test",
        content_type=ContentType.SKILL,
        is_global=False,
    )
    assert not skill_dir.exists()


def test_create_canonical_storage_invalid_name_rejected(tmp_path: Path) -> None:
    """Names with path traversal chars must be rejected."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("test")
    with pytest.raises(ValueError, match="Invalid name"):
        create_canonical_storage(
            source_dir=source_dir,
            project_dir=tmp_path / "project",
            name="../evil",
            content_type=ContentType.SKILL,
            is_global=False,
        )


def test_install_to_all_agents_with_plugin_content_type(tmp_path: Path) -> None:
    """Plugin skills must be installed to agents even when content_type is PLUGIN.

    The caller (add.py) must pass ContentType.SKILL so that install_to_all_agents
    does not early-return.
    """
    from openforge.installer import install_to_all_agents

    skill_dir = tmp_path / "project" / ".agents" / "skills" / "helper"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: helper\n---\n")

    agent = _make_agent(tmp_path)
    skills = [SkillInfo(name="helper", path=str(skill_dir))]

    with patch("openforge.installer.detect_agents", return_value=[agent]):
        installed = install_to_all_agents(
            skills=skills,
            project_dir=tmp_path / "project",
            content_type=ContentType.SKILL,
            is_global=False,
        )

    assert installed == ["test-agent"]
    agent_skill = Path(agent.skills_dir) / "helper"
    assert agent_skill.is_symlink()


def test_create_canonical_storage_preserves_symlinks(tmp_path: Path) -> None:
    """copytree should preserve symlinks rather than following them."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "real.txt").write_text("real content")
    (source_dir / "link.txt").symlink_to(source_dir / "real.txt")

    dest = create_canonical_storage(
        source_dir=source_dir,
        project_dir=tmp_path / "project",
        name="test-skill",
        content_type=ContentType.SKILL,
        is_global=False,
    )
    link = dest / "link.txt"
    assert link.is_symlink(), "Symlinks should be preserved, not followed"
