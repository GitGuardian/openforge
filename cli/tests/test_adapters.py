# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

from openforge.agents.adapters.claude import install_mcp_config, install_commands, install_hooks


def test_install_mcp_config(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / ".mcp.json").write_text(json.dumps({
        "mcpServers": {
            "my-server": {"command": "node", "args": ["server.js"]}
        }
    }))

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    install_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)

    mcp_path = project_dir / ".mcp.json"
    assert mcp_path.exists()
    data = json.loads(mcp_path.read_text())
    assert "my-server" in data["mcpServers"]


def test_install_mcp_config_merges_existing(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / ".mcp.json").write_text(json.dumps({
        "mcpServers": {"new-server": {"command": "new"}}
    }))

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".mcp.json").write_text(json.dumps({
        "mcpServers": {"existing-server": {"command": "old"}}
    }))

    install_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)

    data = json.loads((project_dir / ".mcp.json").read_text())
    assert "existing-server" in data["mcpServers"]
    assert "new-server" in data["mcpServers"]


def test_install_commands(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(parents=True)
    (commands_dir / "deploy.md").write_text("# Deploy\nDeploy the app.")

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    install_commands(plugin_dir=plugin_dir, project_dir=project_dir)

    dest = project_dir / ".claude" / "commands" / "deploy.md"
    assert dest.exists()


def test_install_hooks(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "hooks.json").write_text(json.dumps({"hooks": []}))

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    install_hooks(plugin_dir=plugin_dir, project_dir=project_dir)

    dest = project_dir / ".claude" / "hooks" / "hooks.json"
    assert dest.exists()
