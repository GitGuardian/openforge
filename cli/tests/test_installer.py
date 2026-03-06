from __future__ import annotations

from pathlib import Path

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
