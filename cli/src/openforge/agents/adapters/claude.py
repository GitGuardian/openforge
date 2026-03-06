from __future__ import annotations

import json
import shutil
from pathlib import Path


def install_mcp_config(*, plugin_dir: Path, project_dir: Path) -> None:
    """Read .mcp.json from plugin_dir and merge into project_dir's .mcp.json."""
    source = plugin_dir / ".mcp.json"
    if not source.exists():
        return

    plugin_data: dict[str, dict[str, object]] = json.loads(source.read_text())
    plugin_servers: dict[str, object] = plugin_data.get("mcpServers", {})

    dest = project_dir / ".mcp.json"
    if dest.exists():
        existing_data: dict[str, dict[str, object]] = json.loads(dest.read_text())
    else:
        existing_data = {"mcpServers": {}}

    existing_servers = existing_data.setdefault("mcpServers", {})
    existing_servers.update(plugin_servers)

    dest.write_text(json.dumps(existing_data, indent=2) + "\n")


def remove_mcp_config(*, plugin_dir: Path, project_dir: Path) -> None:
    """Remove the servers that were added by the plugin."""
    source = plugin_dir / ".mcp.json"
    dest = project_dir / ".mcp.json"
    if not source.exists() or not dest.exists():
        return

    plugin_data: dict[str, dict[str, object]] = json.loads(source.read_text())
    plugin_servers = plugin_data.get("mcpServers", {})

    existing_data: dict[str, dict[str, object]] = json.loads(dest.read_text())
    existing_servers = existing_data.get("mcpServers", {})

    for key in plugin_servers:
        existing_servers.pop(key, None)

    dest.write_text(json.dumps(existing_data, indent=2) + "\n")


def install_commands(*, plugin_dir: Path, project_dir: Path) -> None:
    """Copy all .md files from plugin_dir/commands/ to project_dir/.claude/commands/."""
    source_dir = plugin_dir / "commands"
    if not source_dir.exists():
        return

    dest_dir = project_dir / ".claude" / "commands"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for md_file in source_dir.glob("*.md"):
        shutil.copy2(md_file, dest_dir / md_file.name)


def remove_commands(*, plugin_dir: Path, project_dir: Path) -> None:
    """Remove command files that were installed by the plugin."""
    source_dir = plugin_dir / "commands"
    if not source_dir.exists():
        return

    dest_dir = project_dir / ".claude" / "commands"
    for md_file in source_dir.glob("*.md"):
        target = dest_dir / md_file.name
        if target.exists():
            target.unlink()


def install_hooks(*, plugin_dir: Path, project_dir: Path) -> None:
    """Copy hooks/hooks.json to project_dir/.claude/hooks/hooks.json."""
    source = plugin_dir / "hooks" / "hooks.json"
    if not source.exists():
        return

    dest_dir = project_dir / ".claude" / "hooks"
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, dest_dir / "hooks.json")


def remove_hooks(*, plugin_dir: Path, project_dir: Path) -> None:
    """Remove hooks that were installed by the plugin."""
    dest = project_dir / ".claude" / "hooks" / "hooks.json"
    if dest.exists():
        dest.unlink()
