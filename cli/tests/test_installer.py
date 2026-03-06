# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from openforge.agents.base import AgentConfig
from openforge.installer import (
    _canonical_base,
    _resolve_skills_dir,
    create_canonical_storage,
    install_skills_to_agent,
    install_to_all_agents,
    remove_canonical_storage,
    remove_skills_from_agent,
)
from openforge.types import ContentType, SkillInfo


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


def test_create_canonical_storage_global(tmp_path: Path) -> None:
    """Global storage uses ~/.config/openforge/skills/."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("test")

    with patch("openforge.installer.Path.home", return_value=tmp_path):
        dest = create_canonical_storage(
            source_dir=source_dir,
            project_dir=tmp_path / "project",
            name="global-skill",
            content_type=ContentType.SKILL,
            is_global=True,
        )
    assert dest.exists()
    assert ".config" in str(dest)
    assert "openforge" in str(dest)


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


def test_install_skills_to_agent_replaces_existing_symlink(tmp_path: Path) -> None:
    """Re-installing should replace an existing symlink."""
    skill_dir = tmp_path / "project" / ".agents" / "skills" / "lint"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test")

    agent = _make_agent(tmp_path)
    skills = [SkillInfo(name="lint", path=str(skill_dir))]

    # Install twice
    install_skills_to_agent(agent=agent, skills=skills, project_dir=tmp_path, is_global=False)
    install_skills_to_agent(agent=agent, skills=skills, project_dir=tmp_path, is_global=False)

    agent_skill = Path(agent.skills_dir) / "lint"
    assert agent_skill.is_symlink()


def test_remove_skills_from_agent(tmp_path: Path) -> None:
    """remove_skills_from_agent should remove symlinks for given skill names."""
    agent = _make_agent(tmp_path)
    skills_dir = Path(agent.skills_dir)
    skills_dir.mkdir(parents=True)

    # Create symlinks
    target = tmp_path / "canonical" / "lint"
    target.mkdir(parents=True)
    (skills_dir / "lint").symlink_to(target)
    (skills_dir / "format").symlink_to(target)

    remove_skills_from_agent(
        agent=agent,
        skill_names=["lint", "format"],
        project_dir=tmp_path,
        is_global=False,
    )

    assert not (skills_dir / "lint").exists()
    assert not (skills_dir / "format").exists()


def test_remove_skills_from_agent_nonexistent(tmp_path: Path) -> None:
    """remove_skills_from_agent should not crash if skill link does not exist."""
    agent = _make_agent(tmp_path)
    skills_dir = Path(agent.skills_dir)
    skills_dir.mkdir(parents=True)

    # Should not raise
    remove_skills_from_agent(
        agent=agent,
        skill_names=["nonexistent"],
        project_dir=tmp_path,
        is_global=False,
    )


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


def test_remove_canonical_storage_nonexistent(tmp_path: Path) -> None:
    """remove_canonical_storage should not crash when dir does not exist."""
    remove_canonical_storage(
        project_dir=tmp_path,
        name="nonexistent",
        content_type=ContentType.SKILL,
        is_global=False,
    )


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
    """install_to_all_agents returns empty list for PLUGIN content type."""
    from openforge.installer import install_to_all_agents

    skill_dir = tmp_path / "project" / ".agents" / "skills" / "helper"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: helper\n---\n")

    skills = [SkillInfo(name="helper", path=str(skill_dir))]

    result = install_to_all_agents(
        skills=skills,
        project_dir=tmp_path / "project",
        content_type=ContentType.PLUGIN,
        is_global=False,
    )
    assert result == []


def test_install_to_all_agents_with_skill_content_type(tmp_path: Path) -> None:
    """install_to_all_agents installs skills when content_type is SKILL."""
    agent = _make_agent(tmp_path)
    skill_dir = tmp_path / "project" / ".agents" / "skills" / "helper"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test")

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


def test_install_to_all_agents_target_agent(tmp_path: Path) -> None:
    """install_to_all_agents with target_agent only installs to that agent."""
    agent = _make_agent(tmp_path)
    skill_dir = tmp_path / "project" / ".agents" / "skills" / "helper"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test")

    skills = [SkillInfo(name="helper", path=str(skill_dir))]

    with patch("openforge.installer.get_agent", return_value=agent):
        installed = install_to_all_agents(
            skills=skills,
            project_dir=tmp_path / "project",
            content_type=ContentType.SKILL,
            is_global=False,
            target_agent="test-agent",
        )

    assert installed == ["test-agent"]


def test_install_to_all_agents_target_agent_not_found(tmp_path: Path) -> None:
    """install_to_all_agents with unknown target_agent returns empty."""
    skills = [SkillInfo(name="helper", path="/fake")]

    with patch("openforge.installer.get_agent", return_value=None):
        installed = install_to_all_agents(
            skills=skills,
            project_dir=tmp_path,
            content_type=ContentType.SKILL,
            is_global=False,
            target_agent="nonexistent",
        )

    assert installed == []


def test_resolve_skills_dir_global_raises_when_not_supported(tmp_path: Path) -> None:
    """_resolve_skills_dir raises ValueError for agents without global_skills_dir."""
    agent = _make_agent(tmp_path)  # global_skills_dir is None

    with pytest.raises(ValueError, match="does not support global"):
        _resolve_skills_dir(agent, is_global=True)


def test_resolve_skills_dir_global(tmp_path: Path) -> None:
    """_resolve_skills_dir returns expanded global_skills_dir when is_global=True."""
    agent = AgentConfig(
        name="test-agent",
        display_name="Test Agent",
        skills_dir=str(tmp_path / "local"),
        global_skills_dir=str(tmp_path / "global"),
        detect=lambda: True,
    )
    result = _resolve_skills_dir(agent, is_global=True)
    assert result == tmp_path / "global"


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


def test_create_canonical_storage_overwrites_existing(tmp_path: Path) -> None:
    """Re-creating canonical storage should overwrite the previous version."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("version 1")

    project_dir = tmp_path / "project"
    dest1 = create_canonical_storage(
        source_dir=source_dir,
        project_dir=project_dir,
        name="test",
        content_type=ContentType.SKILL,
        is_global=False,
    )
    assert (dest1 / "SKILL.md").read_text() == "version 1"

    # Update source and re-create
    (source_dir / "SKILL.md").write_text("version 2")
    dest2 = create_canonical_storage(
        source_dir=source_dir,
        project_dir=project_dir,
        name="test",
        content_type=ContentType.SKILL,
        is_global=False,
    )
    assert dest1 == dest2
    assert (dest2 / "SKILL.md").read_text() == "version 2"


def test_canonical_base_local_skill(tmp_path: Path) -> None:
    """_canonical_base returns .agents/skills/ for local skill."""
    result = _canonical_base(tmp_path, ContentType.SKILL, is_global=False)
    assert result == tmp_path / ".agents" / "skills"


def test_canonical_base_local_plugin(tmp_path: Path) -> None:
    """_canonical_base returns .agents/plugins/ for local plugin."""
    result = _canonical_base(tmp_path, ContentType.PLUGIN, is_global=False)
    assert result == tmp_path / ".agents" / "plugins"
