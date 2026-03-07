# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

from openforge.agents.adapters.claude import (
    install_commands,
    install_hooks,
    install_mcp_config,
    remove_commands,
    remove_hooks,
    remove_mcp_config,
)


def test_install_mcp_config(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"my-server": {"command": "node", "args": ["server.js"]}}})
    )

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
    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"new-server": {"command": "new"}}})
    )

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"existing-server": {"command": "old"}}})
    )

    install_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)

    data = json.loads((project_dir / ".mcp.json").read_text())
    assert "existing-server" in data["mcpServers"]
    assert "new-server" in data["mcpServers"]


def test_install_mcp_config_no_source(tmp_path: Path) -> None:
    """install_mcp_config is a no-op when .mcp.json does not exist."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    install_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)
    assert not (project_dir / ".mcp.json").exists()


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


def test_install_commands_no_source(tmp_path: Path) -> None:
    """install_commands is a no-op when commands/ does not exist."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    install_commands(plugin_dir=plugin_dir, project_dir=project_dir)
    assert not (project_dir / ".claude" / "commands").exists()


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


def test_install_hooks_no_source(tmp_path: Path) -> None:
    """install_hooks is a no-op when hooks/hooks.json does not exist."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    install_hooks(plugin_dir=plugin_dir, project_dir=project_dir)
    assert not (project_dir / ".claude" / "hooks").exists()


def test_remove_mcp_config(tmp_path: Path) -> None:
    """remove_mcp_config removes servers added by the plugin."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"plugin-server": {"command": "node"}}})
    )

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "plugin-server": {"command": "node"},
                    "other-server": {"command": "python"},
                }
            }
        )
    )

    remove_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)

    data = json.loads((project_dir / ".mcp.json").read_text())
    assert "plugin-server" not in data["mcpServers"]
    assert "other-server" in data["mcpServers"]


def test_remove_mcp_config_no_source(tmp_path: Path) -> None:
    """remove_mcp_config is a no-op when plugin .mcp.json does not exist."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".mcp.json").write_text(json.dumps({"mcpServers": {"keep": {}}}))

    remove_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)

    data = json.loads((project_dir / ".mcp.json").read_text())
    assert "keep" in data["mcpServers"]


def test_remove_mcp_config_no_dest(tmp_path: Path) -> None:
    """remove_mcp_config is a no-op when project .mcp.json does not exist."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / ".mcp.json").write_text(json.dumps({"mcpServers": {"srv": {}}}))

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Should not crash
    remove_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)


def test_remove_commands(tmp_path: Path) -> None:
    """remove_commands removes command files installed by the plugin."""
    plugin_dir = tmp_path / "plugin"
    cmds_src = plugin_dir / "commands"
    cmds_src.mkdir(parents=True)
    (cmds_src / "deploy.md").write_text("# Deploy")
    (cmds_src / "review.md").write_text("# Review")

    project_dir = tmp_path / "project"
    cmds_dest = project_dir / ".claude" / "commands"
    cmds_dest.mkdir(parents=True)
    (cmds_dest / "deploy.md").write_text("# Deploy")
    (cmds_dest / "review.md").write_text("# Review")
    (cmds_dest / "other.md").write_text("# Other")

    remove_commands(plugin_dir=plugin_dir, project_dir=project_dir)

    assert not (cmds_dest / "deploy.md").exists()
    assert not (cmds_dest / "review.md").exists()
    assert (cmds_dest / "other.md").exists()


def test_remove_commands_no_source(tmp_path: Path) -> None:
    """remove_commands is a no-op when plugin has no commands/ dir."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    remove_commands(plugin_dir=plugin_dir, project_dir=project_dir)


def test_remove_hooks(tmp_path: Path) -> None:
    """remove_hooks removes the hooks.json file."""
    project_dir = tmp_path / "project"
    hooks_dir = project_dir / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "hooks.json").write_text(json.dumps({"hooks": []}))

    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    remove_hooks(plugin_dir=plugin_dir, project_dir=project_dir)

    assert not (hooks_dir / "hooks.json").exists()


def test_remove_hooks_no_file(tmp_path: Path) -> None:
    """remove_hooks is a no-op when hooks.json does not exist."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()

    # Should not crash
    remove_hooks(plugin_dir=plugin_dir, project_dir=project_dir)


def test_install_remove_roundtrip(tmp_path: Path) -> None:
    """Install then remove: project should be back to original state."""
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"roundtrip-srv": {"command": "node"}}})
    )
    cmds_src = plugin_dir / "commands"
    cmds_src.mkdir()
    (cmds_src / "test.md").write_text("# Test")
    hooks_src = plugin_dir / "hooks"
    hooks_src.mkdir()
    (hooks_src / "hooks.json").write_text(json.dumps({"hooks": []}))

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Install
    install_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)
    install_commands(plugin_dir=plugin_dir, project_dir=project_dir)
    install_hooks(plugin_dir=plugin_dir, project_dir=project_dir)

    # Verify installed
    assert (project_dir / ".mcp.json").exists()
    assert (project_dir / ".claude" / "commands" / "test.md").exists()
    assert (project_dir / ".claude" / "hooks" / "hooks.json").exists()

    # Remove
    remove_mcp_config(plugin_dir=plugin_dir, project_dir=project_dir)
    remove_commands(plugin_dir=plugin_dir, project_dir=project_dir)
    remove_hooks(plugin_dir=plugin_dir, project_dir=project_dir)

    # MCP servers should be empty
    mcp_data = json.loads((project_dir / ".mcp.json").read_text())
    assert mcp_data["mcpServers"] == {}
    # Commands and hooks files should be gone
    assert not (project_dir / ".claude" / "commands" / "test.md").exists()
    assert not (project_dir / ".claude" / "hooks" / "hooks.json").exists()
