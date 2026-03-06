# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest

from openforge.plugins import parse_plugin, parse_marketplace, detect_content
from openforge.types import ContentType


def test_parse_plugin_json(tmp_path: Path) -> None:
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({
        "name": "my-plugin",
        "description": "A test plugin",
    }))
    skills_dir = tmp_path / "skills" / "skill-a"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: skill-a\n---\n")
    plugin = parse_plugin(tmp_path)
    assert plugin.name == "my-plugin"
    assert plugin.description == "A test plugin"
    assert len(plugin.skills) == 1


def test_parse_plugin_with_mcp(tmp_path: Path) -> None:
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "mcp-plugin"}))
    (tmp_path / ".mcp.json").write_text("{}")
    plugin = parse_plugin(tmp_path)
    assert plugin.has_mcp is True


def test_parse_plugin_with_commands(tmp_path: Path) -> None:
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "cmd-plugin"}))
    commands_dir = tmp_path / "commands"
    commands_dir.mkdir()
    (commands_dir / "deploy.md").write_text("# Deploy")
    plugin = parse_plugin(tmp_path)
    assert plugin.has_commands is True


def test_parse_marketplace_json(tmp_path: Path) -> None:
    (tmp_path / "marketplace.json").write_text(json.dumps({
        "plugins": [
            {"name": "plugin-a", "path": "plugins/a"},
            {"name": "plugin-b", "path": "plugins/b"},
        ]
    }))
    for name in ["a", "b"]:
        p = tmp_path / "plugins" / name / ".claude-plugin"
        p.mkdir(parents=True)
        (p / "plugin.json").write_text(json.dumps({"name": f"plugin-{name}"}))
    plugins = parse_marketplace(tmp_path)
    assert len(plugins) == 2


def test_detect_content_plugin(tmp_path: Path) -> None:
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "my-plugin"}))
    content = detect_content(tmp_path)
    assert content.content_type == ContentType.PLUGIN
    assert content.plugin is not None


def test_detect_content_skill(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills" / "lint"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: lint\n---\n")
    content = detect_content(tmp_path)
    assert content.content_type == ContentType.SKILL
    assert len(content.skills) == 1


def test_parse_plugin_invalid_name_rejected(tmp_path: Path) -> None:
    """Plugin names with invalid chars must be rejected."""
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({"name": "../evil"}))
    with pytest.raises(ValueError, match="Invalid plugin name"):
        parse_plugin(tmp_path)


def test_detect_content_marketplace_returns_all_plugins(tmp_path: Path) -> None:
    """detect_content for a marketplace with 2 plugins must expose all plugins."""
    (tmp_path / "marketplace.json").write_text(json.dumps({
        "plugins": [
            {"name": "plugin-a", "path": "plugins/a"},
            {"name": "plugin-b", "path": "plugins/b"},
        ]
    }))
    for name in ["a", "b"]:
        p = tmp_path / "plugins" / name / ".claude-plugin"
        p.mkdir(parents=True)
        (p / "plugin.json").write_text(json.dumps({"name": f"plugin-{name}"}))
        # Add an MCP config to plugin-a
        if name == "a":
            (tmp_path / "plugins" / name / ".mcp.json").write_text(
                json.dumps({"mcpServers": {"server-a": {"command": "echo"}}})
            )
        # Add commands to plugin-b
        if name == "b":
            cmds = tmp_path / "plugins" / name / "commands"
            cmds.mkdir()
            (cmds / "deploy.md").write_text("# Deploy")

    content = detect_content(tmp_path)
    assert content.content_type == ContentType.PLUGIN
    # Must have all plugins accessible
    assert content.plugins is not None
    assert len(content.plugins) == 2
    plugin_names = {p.name for p in content.plugins}
    assert plugin_names == {"plugin-a", "plugin-b"}


def test_parse_marketplace_path_traversal_rejected(tmp_path: Path) -> None:
    """Marketplace plugin paths that escape root must be rejected."""
    (tmp_path / "marketplace.json").write_text(json.dumps({
        "plugins": [{"name": "evil", "path": "../../etc"}]
    }))
    with pytest.raises(ValueError, match="Path escape detected"):
        parse_marketplace(tmp_path)
