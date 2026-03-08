# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import datetime
import json
import subprocess  # nosec B404
import tempfile
from pathlib import Path
from typing import Any, cast

import typer
from rich.console import Console
from rich.table import Table

from openforge.agents.adapters import claude as claude_adapter
from openforge.agents.adapters import cursor as cursor_adapter
from openforge.agents.registry import detect_agents
from openforge.cli import get_project_dir
from openforge.installer import create_canonical_storage, install_to_all_agents
from openforge.lock import add_lock_entry, lock_file_path
from openforge.plugins import detect_content
from openforge.providers.forge import ForgeProvider
from openforge.providers.git import GitProvider
from openforge.providers.local import LocalProvider
from openforge.providers.source_parser import parse_source
from openforge.providers.wellknown import WellKnownProvider
from openforge.telemetry import send_event
from openforge.types import (
    ContentType,
    LockEntry,
    PluginInfo,
    SkillInfo,
    Source,
)

_console = Console()

_PROVIDERS = [GitProvider(), LocalProvider(), WellKnownProvider(), ForgeProvider()]


def get_provider(
    source: Source,
) -> GitProvider | LocalProvider | WellKnownProvider | ForgeProvider:
    """Return the first provider that matches the source."""
    for p in _PROVIDERS:
        if p.matches(source):
            return p
    msg = f"No provider for source type: {source.source_type.value}"
    raise ValueError(msg)


def _collect_mcp_servers(plugin_dir: Path) -> dict[str, str]:
    """Read .mcp.json and return a mapping of server name to command string."""
    mcp_path = plugin_dir / ".mcp.json"
    if not mcp_path.is_file():
        return {}
    data = cast(dict[str, Any], json.loads(mcp_path.read_text(encoding="utf-8")))
    servers = cast(dict[str, Any], data.get("mcpServers", {}))
    result: dict[str, str] = {}
    for name, config in servers.items():
        if not isinstance(config, dict):
            result[str(name)] = str(config)
            continue
        typed_config = cast(dict[str, Any], config)
        cmd: str = str(typed_config.get("command", ""))
        args_val: object = typed_config.get("args", [])
        if isinstance(args_val, list):
            args_list = cast(list[Any], args_val)
            cmd_str = f"{cmd} {' '.join(str(a) for a in args_list)}".strip()
        else:
            cmd_str = cmd
        result[str(name)] = cmd_str
    return result


def _collect_hooks(plugin_dir: Path) -> list[tuple[str, str]]:
    """Read hooks.json and return a list of (event, command) tuples."""
    # Check both possible locations for hooks.json
    hooks_path = plugin_dir / ".claude" / "hooks.json"
    if not hooks_path.is_file():
        hooks_path = plugin_dir / "hooks" / "hooks.json"
    if not hooks_path.is_file():
        return []
    data = cast(dict[str, Any], json.loads(hooks_path.read_text(encoding="utf-8")))
    result: list[tuple[str, str]] = []
    # hooks.json can be {"hooks": [...]} or {"PreToolUse": [...], ...}
    hooks_val: Any = data.get("hooks", data)
    if isinstance(hooks_val, dict):
        hooks_dict = cast(dict[str, Any], hooks_val)
        for event_name, entries in hooks_dict.items():
            if not isinstance(entries, list):
                continue
            entries_list = cast(list[Any], entries)
            for entry in entries_list:
                if not isinstance(entry, dict):
                    continue
                typed_entry = cast(dict[str, Any], entry)
                cmd = str(typed_entry.get("command", ""))
                result.append((str(event_name), cmd))
    elif isinstance(hooks_val, list):
        hooks_list = cast(list[Any], hooks_val)
        for entry in hooks_list:
            if not isinstance(entry, dict):
                continue
            typed_entry2 = cast(dict[str, Any], entry)
            event = str(typed_entry2.get("event", ""))
            cmd = str(typed_entry2.get("command", ""))
            result.append((event, cmd))
    return result


def _collect_commands(plugin_dir: Path) -> list[str]:
    """List command file names from plugin_dir/commands/."""
    commands_dir = plugin_dir / "commands"
    if not commands_dir.is_dir():
        return []
    return sorted(f.name for f in commands_dir.iterdir() if f.is_file())


def _has_executable_capabilities(plugin: PluginInfo) -> bool:
    """Return True if the plugin has any executable capabilities (MCP, hooks, commands)."""
    return plugin.has_mcp or plugin.has_hooks or plugin.has_commands


def _display_capabilities_and_confirm(
    plugin: PluginInfo,
    plugin_dir: Path,
    *,
    auto_confirm: bool,
) -> bool:
    """Display what the plugin wants to install and ask for confirmation.

    Returns True if the user confirms, False otherwise.
    """
    if not _has_executable_capabilities(plugin):
        return True

    _console.print(f'\nPlugin "{plugin.name}" wants to install:\n')

    if plugin.has_mcp:
        servers = _collect_mcp_servers(plugin_dir)
        if servers:
            _console.print("  [bold]MCP Servers:[/bold]")
            for name, cmd in servers.items():
                _console.print(f"    - {name} (command: {cmd})")
            _console.print()

    if plugin.has_hooks:
        hooks = _collect_hooks(plugin_dir)
        if hooks:
            _console.print("  [bold]Hooks:[/bold]")
            for event, cmd in hooks:
                _console.print(f"    - {event}: {cmd}")
            _console.print()

    if plugin.has_commands:
        commands = _collect_commands(plugin_dir)
        if commands:
            _console.print("  [bold]Commands:[/bold]")
            for cmd_name in commands:
                _console.print(f"    - {cmd_name}")
            _console.print()

    if auto_confirm:
        return True

    return typer.confirm("Install these plugin capabilities?", default=False)


def _install_plugin_capabilities(
    plugin: PluginInfo,
    plugin_dir: Path,
    project_dir: Path,
    target_agent: str | None = None,
) -> None:
    """Dispatch plugin capability installation to the appropriate agent adapters."""
    agents = detect_agents()
    if target_agent is not None:
        agents = [a for a in agents if a.name == target_agent]
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
    source: str = typer.Argument(..., help="Plugin/skill source (owner/repo, owner/repo@skill)"),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Target specific agent"),
    is_global: bool = typer.Option(False, "--global", "-g", help="Install globally"),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Auto-confirm plugin capability installation"
    ),
) -> None:
    """Add a plugin or skill from a source."""
    parsed = parse_source(source)
    project_dir = get_project_dir()

    try:
        provider = get_provider(parsed)
    except ValueError as e:
        _console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from None

    with tempfile.TemporaryDirectory(prefix="openforge-") as tmp_str:
        tmp_dir = Path(tmp_str)
        try:
            fetch_result = provider.fetch(parsed, tmp_dir)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            err_msg = getattr(e, "stderr", None) or str(e)
            _console.print(f"[red]Failed to fetch {parsed.shorthand}: {err_msg.strip()}[/red]")
            raise typer.Exit(code=1) from None
        content_root = fetch_result.content_root
        git_sha = fetch_result.sha
        detected = detect_content(content_root)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        lock_path = lock_file_path(project_dir, is_global=is_global)

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
                content_type=ContentType.SKILL,
                is_global=is_global,
                target_agent=agent,
            )

        # Install plugin capabilities
        if detected.content_type is ContentType.PLUGIN and detected.plugins:
            for plg in detected.plugins:
                plugin_dir = content_root
                create_canonical_storage(
                    source_dir=plugin_dir,
                    project_dir=project_dir,
                    name=plg.name,
                    content_type=ContentType.PLUGIN,
                    is_global=is_global,
                )
                confirmed = _display_capabilities_and_confirm(plg, plugin_dir, auto_confirm=yes)
                if confirmed:
                    _install_plugin_capabilities(plg, plugin_dir, project_dir, agent)
                else:
                    _console.print("[yellow]Skipped plugin capability installation.[/yellow]")

        # Write lock entry
        skill_names = tuple(s.name for s in skills)
        entry = LockEntry(
            type=detected.content_type,
            source=parsed.shorthand,
            source_type=parsed.source_type,
            git_url=parsed.git_url,
            git_sha=git_sha,
            skills=skill_names,
            agents_installed=tuple(installed_agents),
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
