from __future__ import annotations

import os
import shutil
from pathlib import Path

from openforge.agents.base import AgentConfig
from openforge.agents.registry import detect_agents, get_agent
from openforge.types import ContentType, SkillInfo
from openforge.validation import validate_name


def _canonical_base(
    project_dir: Path,
    content_type: ContentType,
    is_global: bool,
) -> Path:
    """Return the base directory for canonical storage."""
    subdir = "plugins" if content_type is ContentType.PLUGIN else "skills"
    if is_global:
        return Path.home() / ".config" / "openforge" / subdir
    return project_dir / ".agents" / subdir


def create_canonical_storage(
    source_dir: Path,
    project_dir: Path,
    name: str,
    content_type: ContentType,
    is_global: bool,
) -> Path:
    """Copy fetched content to the canonical storage location.

    Returns the destination path.
    """
    validate_name(name)
    base = _canonical_base(project_dir, content_type, is_global)
    dest = base / name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source_dir, dest, symlinks=True)
    return dest


def remove_canonical_storage(
    project_dir: Path,
    name: str,
    content_type: ContentType,
    is_global: bool,
) -> None:
    """Delete the canonical directory for *name*."""
    base = _canonical_base(project_dir, content_type, is_global)
    dest = base / name
    if dest.exists():
        shutil.rmtree(dest)


def _resolve_skills_dir(agent: AgentConfig, is_global: bool) -> Path:
    """Return the resolved skills directory for an agent."""
    if is_global:
        raw = agent.global_skills_dir
        if raw is None:
            msg = f"Agent {agent.name!r} does not support global skills"
            raise ValueError(msg)
        return Path(raw).expanduser()
    return Path(agent.skills_dir)


def install_skills_to_agent(
    agent: AgentConfig,
    skills: list[SkillInfo],
    project_dir: Path,
    is_global: bool,
) -> None:
    """Create symlinks from the agent's skills dir to canonical locations."""
    skills_dir = _resolve_skills_dir(agent, is_global)
    skills_dir.mkdir(parents=True, exist_ok=True)

    for skill in skills:
        skill_path = Path(skill.path)
        link = skills_dir / skill.name
        if link.exists() or link.is_symlink():
            link.unlink()

        # Use relative symlinks where possible.
        try:
            rel = os.path.relpath(skill_path, skills_dir)
            link.symlink_to(rel)
        except ValueError:
            # On Windows, relpath can fail across drives.
            link.symlink_to(skill_path)


def remove_skills_from_agent(
    agent: AgentConfig,
    skill_names: list[str],
    project_dir: Path,
    is_global: bool,
) -> None:
    """Remove symlinks for the given skill names from the agent's skills dir."""
    skills_dir = _resolve_skills_dir(agent, is_global)

    for name in skill_names:
        link = skills_dir / name
        if link.is_symlink() or link.exists():
            link.unlink()


def install_to_all_agents(
    skills: list[SkillInfo],
    project_dir: Path,
    content_type: ContentType,
    is_global: bool,
    target_agent: str | None = None,
) -> list[str]:
    """Install skills to detected agents (or a specific target).

    Returns a list of agent names that were installed to.
    """
    if content_type is not ContentType.SKILL:
        return []

    agents: list[AgentConfig]
    if target_agent is not None:
        agent = get_agent(target_agent)
        if agent is None:
            return []
        agents = [agent]
    else:
        agents = detect_agents()

    installed: list[str] = []
    for agent in agents:
        install_skills_to_agent(
            agent=agent,
            skills=skills,
            project_dir=project_dir,
            is_global=is_global,
        )
        installed.append(agent.name)

    return installed
