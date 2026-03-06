from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from openforge.skills import find_skills_in_dir
from openforge.types import ContentType, DetectedContent, PluginInfo


def parse_plugin(root: Path) -> PluginInfo:
    """Parse .claude-plugin/plugin.json and detect capabilities."""
    plugin_json_path = root / ".claude-plugin" / "plugin.json"
    data: dict[str, Any] = json.loads(plugin_json_path.read_text(encoding="utf-8"))

    name = str(data.get("name", root.name))
    description = str(data.get("description", ""))

    skills = tuple(find_skills_in_dir(root))

    has_mcp = (root / ".mcp.json").is_file()
    has_commands = (root / "commands").is_dir() and any((root / "commands").iterdir())
    has_hooks = (root / ".claude" / "hooks.json").is_file()
    has_agents = (root / "agents").is_dir() and any((root / "agents").iterdir())
    has_env = (root / ".env.example").is_file() or (root / ".env.template").is_file()

    return PluginInfo(
        name=name,
        description=description,
        skills=skills,
        has_mcp=has_mcp,
        has_commands=has_commands,
        has_hooks=has_hooks,
        has_agents=has_agents,
        has_env=has_env,
    )


def parse_marketplace(root: Path) -> list[PluginInfo]:
    """Parse marketplace.json which lists multiple plugins with their paths."""
    marketplace_path = root / "marketplace.json"
    data: dict[str, Any] = json.loads(marketplace_path.read_text(encoding="utf-8"))

    plugins_list: list[dict[str, Any]] = data.get("plugins", [])

    results: list[PluginInfo] = []
    for entry in plugins_list:
        path_str: str = entry.get("path", "")
        if not path_str:
            continue
        plugin_root = root / path_str
        results.append(parse_plugin(plugin_root))

    return results


def detect_content(root: Path) -> DetectedContent:
    """Determine if a repo contains a plugin, marketplace, or standalone skills."""
    # 1. Single plugin
    if (root / ".claude-plugin" / "plugin.json").is_file():
        plugin = parse_plugin(root)
        return DetectedContent(
            content_type=ContentType.PLUGIN,
            plugin=plugin,
            skills=plugin.skills,
        )

    # 2. Multi-plugin marketplace
    if (root / "marketplace.json").is_file():
        plugins = parse_marketplace(root)
        all_skills = tuple(s for p in plugins for s in p.skills)
        return DetectedContent(
            content_type=ContentType.PLUGIN,
            plugin=plugins[0] if plugins else None,
            skills=all_skills,
        )

    # 3. Standalone skills
    skills = tuple(find_skills_in_dir(root))
    return DetectedContent(
        content_type=ContentType.SKILL,
        skills=skills,
    )
