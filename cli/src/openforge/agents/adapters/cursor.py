from __future__ import annotations

import json
import shutil
from pathlib import Path


def install_mcp_config(*, plugin_dir: Path, project_dir: Path) -> None:
    """Read ``.mcp.json`` from *plugin_dir* and merge into ``project_dir/.cursor/mcp.json``."""
    source_path = plugin_dir / ".mcp.json"
    source_data: dict[str, dict[str, object]] = json.loads(source_path.read_text())
    new_servers: dict[str, object] = source_data.get("mcpServers", {})

    cursor_dir = project_dir / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    mcp_path = cursor_dir / "mcp.json"

    existing_data: dict[str, dict[str, object]]
    if mcp_path.exists():
        existing_data = json.loads(mcp_path.read_text())
    else:
        existing_data = {"mcpServers": {}}

    existing_servers = existing_data.setdefault("mcpServers", {})
    existing_servers.update(new_servers)

    mcp_path.write_text(json.dumps(existing_data, indent=2) + "\n")


def install_commands(*, plugin_dir: Path, project_dir: Path) -> None:
    """Copy all ``.md`` files from ``plugin_dir/commands/`` to ``project_dir/.cursor/commands/``."""
    source_commands = plugin_dir / "commands"
    if not source_commands.is_dir():
        return

    dest_commands = project_dir / ".cursor" / "commands"
    dest_commands.mkdir(parents=True, exist_ok=True)

    for md_file in source_commands.glob("*.md"):
        shutil.copy2(md_file, dest_commands / md_file.name)


def remove_mcp_config(*, plugin_dir: Path, project_dir: Path) -> None:
    """Remove servers originally added from *plugin_dir* out of ``project_dir/.cursor/mcp.json``."""
    source_path = plugin_dir / ".mcp.json"
    if not source_path.exists():
        return

    mcp_path = project_dir / ".cursor" / "mcp.json"
    if not mcp_path.exists():
        return

    source_data: dict[str, dict[str, object]] = json.loads(source_path.read_text())
    keys_to_remove: set[str] = set(source_data.get("mcpServers", {}))

    existing_data: dict[str, dict[str, object]] = json.loads(mcp_path.read_text())
    existing_servers = existing_data.get("mcpServers", {})

    for key in keys_to_remove:
        existing_servers.pop(key, None)

    mcp_path.write_text(json.dumps(existing_data, indent=2) + "\n")


def remove_commands(*, plugin_dir: Path, project_dir: Path) -> None:
    """Remove command files that were installed from *plugin_dir*."""
    source_commands = plugin_dir / "commands"
    if not source_commands.is_dir():
        return

    dest_commands = project_dir / ".cursor" / "commands"
    if not dest_commands.is_dir():
        return

    for md_file in source_commands.glob("*.md"):
        target = dest_commands / md_file.name
        if target.exists():
            target.unlink()
