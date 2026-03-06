# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

from openforge.agents.adapters.cursor import install_commands, install_mcp_config


def test_cursor_install_mcp_config(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "my-server": {"command": "node", "args": ["server.js"]}
                }
            }
        )
    )

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    install_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)

    # Cursor uses .cursor/mcp.json
    mcp_path = project_dir / ".cursor" / "mcp.json"
    assert mcp_path.exists()
    data = json.loads(mcp_path.read_text())
    assert "my-server" in data["mcpServers"]


def test_cursor_install_mcp_merges_existing(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"new-server": {"command": "new"}}})
    )

    project_dir = tmp_path / "project"
    cursor_dir = project_dir / ".cursor"
    cursor_dir.mkdir(parents=True)
    (cursor_dir / "mcp.json").write_text(
        json.dumps({"mcpServers": {"existing-server": {"command": "old"}}})
    )

    install_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)

    data = json.loads((cursor_dir / "mcp.json").read_text())
    assert "existing-server" in data["mcpServers"]
    assert "new-server" in data["mcpServers"]


def test_cursor_install_mcp_config_missing_source(tmp_path: Path) -> None:
    """install_mcp_config must not crash when .mcp.json does not exist."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    # No .mcp.json created

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Should return without error, not raise FileNotFoundError
    install_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)

    # No .cursor/mcp.json should be created
    assert not (project_dir / ".cursor" / "mcp.json").exists()


def test_cursor_install_commands(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / "deploy.md").write_text("# Deploy\nDeploy the app.")

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    install_commands(plugin_dir=plugin_dir, project_dir=project_dir)

    dest = project_dir / ".cursor" / "commands" / "deploy.md"
    assert dest.exists()
