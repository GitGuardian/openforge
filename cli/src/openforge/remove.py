from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from openforge.agents.adapters import claude as claude_adapter
from openforge.agents.adapters import cursor as cursor_adapter
from openforge.agents.registry import get_agent
from openforge.cli import get_project_dir, get_user_config_dir
from openforge.installer import remove_canonical_storage, remove_skills_from_agent
from openforge.lock import read_lock, remove_lock_entry
from openforge.telemetry import send_event
from openforge.types import ContentType, LockEntry

_console = Console()


def _lock_file_path(project_dir: Path, is_global: bool) -> Path:
    """Return the lock file path for project-local or global installs."""
    if is_global:
        return get_user_config_dir() / "lock.json"
    return project_dir / ".openforge-lock.json"


def _remove_plugin_capabilities(
    entry: LockEntry,
    plugin_dir: Path,
    project_dir: Path,
) -> None:
    """Remove plugin capability artefacts from agent configurations."""
    if entry.type is not ContentType.PLUGIN:
        return

    for agent_name in entry.agents_installed:
        agent = get_agent(agent_name)
        if agent is None:
            continue

        caps = agent.capabilities
        if agent.name == "claude-code":
            if "mcp" in caps:
                claude_adapter.remove_mcp_config(
                    plugin_dir=plugin_dir,
                    project_dir=project_dir,
                )
            if "commands" in caps:
                claude_adapter.remove_commands(
                    plugin_dir=plugin_dir,
                    project_dir=project_dir,
                )
            if "hooks" in caps:
                claude_adapter.remove_hooks(
                    plugin_dir=plugin_dir,
                    project_dir=project_dir,
                )
        elif agent.name == "cursor":
            if "mcp" in caps:
                cursor_adapter.remove_mcp_config(
                    plugin_dir=plugin_dir,
                    project_dir=project_dir,
                )
            if "commands" in caps:
                cursor_adapter.remove_commands(
                    plugin_dir=plugin_dir,
                    project_dir=project_dir,
                )


def remove_command(
    name: str = typer.Argument(..., help="Name of plugin or skill to remove"),
    is_global: bool = typer.Option(
        False, "--global", "-g", help="Remove from global installation"
    ),
) -> None:
    """Remove an installed plugin or skill."""
    project_dir = get_project_dir()
    lock_path = _lock_file_path(project_dir, is_global)
    lock = read_lock(lock_path)

    entry = lock.entries.get(name)
    if entry is None:
        _console.print(f"[red]{name!r} is not installed (not found in lock file).[/red]")
        raise typer.Exit(code=1)

    # Remove skill symlinks from agents
    if entry.skills and entry.agents_installed:
        for agent_name in entry.agents_installed:
            agent = get_agent(agent_name)
            if agent is not None:
                remove_skills_from_agent(
                    agent=agent,
                    skill_names=entry.skills,
                    project_dir=project_dir,
                    is_global=is_global,
                )

    # Remove plugin capabilities from agents
    if entry.type is ContentType.PLUGIN:
        subdir = "plugins"
        plugin_dir = (
            Path.home() / ".config" / "openforge" / subdir / name
            if is_global
            else project_dir / ".agents" / subdir / name
        )
        _remove_plugin_capabilities(entry, plugin_dir, project_dir)

    # Remove canonical storage
    remove_canonical_storage(
        project_dir=project_dir,
        name=name,
        content_type=entry.type,
        is_global=is_global,
    )

    # Remove lock entry
    remove_lock_entry(lock_path, name)

    # Telemetry
    send_event(
        "remove",
        {
            "name": name,
            "content_type": entry.type.value,
        },
    )

    # Print summary
    _console.print(f"[green]Removed {entry.type.value} {name!r}.[/green]")
