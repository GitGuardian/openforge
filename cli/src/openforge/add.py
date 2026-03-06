from __future__ import annotations

import datetime
import shutil
import subprocess
import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from openforge.agents.adapters import claude as claude_adapter
from openforge.agents.adapters import cursor as cursor_adapter
from openforge.agents.registry import detect_agents
from openforge.cli import get_project_dir, get_user_config_dir
from openforge.installer import create_canonical_storage, install_to_all_agents
from openforge.lock import add_lock_entry
from openforge.plugins import detect_content
from openforge.providers.github import GitHubProvider
from openforge.providers.source_parser import parse_source
from openforge.telemetry import send_event
from openforge.types import (
    ContentType,
    LockEntry,
    PluginInfo,
    SkillInfo,
    SourceType,
)

_console = Console()


def _lock_file_path(project_dir: Path, is_global: bool) -> Path:
    """Return the lock file path for project-local or global installs."""
    if is_global:
        return get_user_config_dir() / "lock.json"
    return project_dir / ".openforge-lock.json"


def _install_plugin_capabilities(
    plugin: PluginInfo,
    plugin_dir: Path,
    project_dir: Path,
) -> None:
    """Dispatch plugin capability installation to the appropriate agent adapters."""
    agents = detect_agents()
    for agent_cfg in agents:
        caps = agent_cfg.capabilities
        if agent_cfg.name == "claude-code":
            if plugin.has_mcp and "mcp" in caps:
                claude_adapter.install_mcp_config(
                    plugin_dir=plugin_dir,
                    project_dir=project_dir,
                )
            if plugin.has_commands and "commands" in caps:
                claude_adapter.install_commands(
                    plugin_dir=plugin_dir,
                    project_dir=project_dir,
                )
            if plugin.has_hooks and "hooks" in caps:
                claude_adapter.install_hooks(
                    plugin_dir=plugin_dir,
                    project_dir=project_dir,
                )
        elif agent_cfg.name == "cursor":
            if plugin.has_mcp and "mcp" in caps:
                cursor_adapter.install_mcp_config(
                    plugin_dir=plugin_dir,
                    project_dir=project_dir,
                )
            if plugin.has_commands and "commands" in caps:
                cursor_adapter.install_commands(
                    plugin_dir=plugin_dir,
                    project_dir=project_dir,
                )


def add_command(
    source: str = typer.Argument(
        ..., help="Plugin/skill source (owner/repo, owner/repo@skill)"
    ),
    agent: str | None = typer.Option(
        None, "--agent", "-a", help="Target specific agent"
    ),
    is_global: bool = typer.Option(
        False, "--global", "-g", help="Install globally"
    ),
) -> None:
    """Add a plugin or skill from a source."""
    parsed = parse_source(source)
    project_dir = get_project_dir()
    provider = GitHubProvider()

    tmp_dir = Path(tempfile.mkdtemp(prefix="openforge-"))
    try:
        try:
            git_sha = provider.fetch(parsed, tmp_dir)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or ""
            _console.print(f"[red]Failed to fetch {parsed.shorthand}: {stderr.strip()}[/red]")
            raise typer.Exit(code=1) from None
        content_root = provider.content_root(parsed, tmp_dir)
        detected = detect_content(content_root)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        lock_path = _lock_file_path(project_dir, is_global)

        skills = list(detected.skills)

        # Filter to a specific skill if requested
        if parsed.skill_name is not None:
            skills = [s for s in skills if s.name == parsed.skill_name]
            if not skills:
                _console.print(
                    f"[red]Skill {parsed.skill_name!r} not found in {parsed.shorthand}[/red]"
                )
                raise typer.Exit(code=1)

        installed_agents: list[str] = []

        # Install skills to canonical storage and update paths
        canonical_skills: list[SkillInfo] = []
        for skill in skills:
            skill_source_dir = content_root / skill.path if skill.path else content_root
            canonical_dest = create_canonical_storage(
                source_dir=skill_source_dir,
                project_dir=project_dir,
                name=skill.name,
                content_type=ContentType.SKILL,
                is_global=is_global,
            )
            canonical_skills.append(
                SkillInfo(
                    name=skill.name,
                    description=skill.description,
                    tags=skill.tags,
                    path=str(canonical_dest),
                )
            )
        skills = canonical_skills

        if skills:
            installed_agents = install_to_all_agents(
                skills=skills,
                project_dir=project_dir,
                content_type=detected.content_type,
                is_global=is_global,
                target_agent=agent,
            )

        # Install plugin capabilities
        if detected.content_type is ContentType.PLUGIN and detected.plugin is not None:
            plugin = detected.plugin
            plugin_dir = content_root
            create_canonical_storage(
                source_dir=plugin_dir,
                project_dir=project_dir,
                name=plugin.name,
                content_type=ContentType.PLUGIN,
                is_global=is_global,
            )
            _install_plugin_capabilities(plugin, plugin_dir, project_dir)

        # Write lock entry
        skill_names = [s.name for s in skills]
        entry = LockEntry(
            type=detected.content_type,
            source=parsed.shorthand,
            source_type=SourceType.GITHUB,
            git_url=parsed.git_url,
            git_sha=git_sha,
            skills=skill_names,
            agents_installed=installed_agents,
            installed_at=now,
            updated_at=now,
        )
        lock_name = parsed.shorthand
        add_lock_entry(lock_path, lock_name, entry)

        # Telemetry
        send_event(
            "add",
            {
                "source": parsed.shorthand,
                "content_type": detected.content_type.value,
                "skills": skill_names,
                "agents": installed_agents,
            },
        )

        # Print summary
        table = Table(title="Installed")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="green")
        table.add_column("Agents", style="yellow")

        for skill in skills:
            table.add_row(
                skill.name,
                "skill",
                ", ".join(installed_agents) if installed_agents else "(none)",
            )

        if detected.content_type is ContentType.PLUGIN and detected.plugin is not None:
            table.add_row(
                detected.plugin.name,
                "plugin",
                ", ".join(installed_agents) if installed_agents else "(none)",
            )

        _console.print(table)

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
