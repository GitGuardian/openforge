# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import typer
from typer.testing import CliRunner

from openforge.lock import write_lock
from openforge.types import ContentType, LockEntry, LockFile, SourceType

runner = CliRunner()


def _make_remove_app() -> typer.Typer:
    from openforge.remove import remove_command

    test_app = typer.Typer()
    test_app.command("remove")(remove_command)
    return test_app


def test_remove_installed_skill(tmp_path: Path) -> None:
    test_app = _make_remove_app()

    # Setup: create canonical storage + lock entry
    project_dir = tmp_path / "project"
    skill_dir = project_dir / ".agents" / "skills" / "lint"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test")

    lock_path = project_dir / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.SKILL,
        source="acme/tools@lint",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/tools",
        git_sha="abc123",
        skills=("lint",),
        agents_installed=(),
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"lint": entry}))

    with patch("openforge.remove.get_project_dir", return_value=project_dir):
        result = runner.invoke(test_app, ["lint"])
        assert result.exit_code == 0, result.output

    assert not skill_dir.exists()


def test_remove_cleans_canonical_by_skill_name(tmp_path: Path) -> None:
    """When lock entry key differs from skill name, canonical dirs for each skill are removed."""
    test_app = _make_remove_app()

    project_dir = tmp_path / "project"
    # Canonical storage uses the skill name, not the lock key
    skill_dir = project_dir / ".agents" / "skills" / "find-skills"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test")

    lock_path = project_dir / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.SKILL,
        source="vercel-labs/skills",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/vercel-labs/skills",
        git_sha="abc123",
        skills=("find-skills",),
        agents_installed=(),
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"vercel-labs/skills": entry}))

    with patch("openforge.remove.get_project_dir", return_value=project_dir):
        result = runner.invoke(test_app, ["vercel-labs/skills"])
        assert result.exit_code == 0, result.output

    # The canonical skill dir should be cleaned up
    assert not skill_dir.exists(), f"Expected {skill_dir} to be removed"


def test_remove_not_found(tmp_path: Path) -> None:
    test_app = _make_remove_app()

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    with patch("openforge.remove.get_project_dir", return_value=project_dir):
        result = runner.invoke(test_app, ["nonexistent"])
        assert result.exit_code != 0
        assert "not installed" in result.output.lower()


def test_remove_plugin_with_capabilities(tmp_path: Path) -> None:
    """Removing a plugin should invoke adapter removal for each capability."""
    test_app = _make_remove_app()

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create plugin canonical storage with MCP, commands, hooks
    plugin_dir = project_dir / ".agents" / "plugins" / "my-plugin"
    plugin_dir.mkdir(parents=True)

    # MCP config
    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"test-server": {"command": "node"}}})
    )

    # Commands
    cmds_dir = plugin_dir / "commands"
    cmds_dir.mkdir()
    (cmds_dir / "deploy.md").write_text("# Deploy")

    # Hooks
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir()
    (hooks_dir / "hooks.json").write_text(json.dumps({"hooks": []}))

    # Project-level .mcp.json (what claude adapter would have written)
    (project_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"test-server": {"command": "node"}}})
    )

    # Project-level .claude/commands/deploy.md
    claude_cmds = project_dir / ".claude" / "commands"
    claude_cmds.mkdir(parents=True)
    (claude_cmds / "deploy.md").write_text("# Deploy")

    # Project-level .claude/hooks/hooks.json
    claude_hooks = project_dir / ".claude" / "hooks"
    claude_hooks.mkdir(parents=True)
    (claude_hooks / "hooks.json").write_text(json.dumps({"hooks": []}))

    # Lock entry
    lock_path = project_dir / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.PLUGIN,
        source="acme/my-plugin",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/my-plugin",
        git_sha="abc123",
        skills=(),
        agents_installed=("claude-code",),
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"my-plugin": entry}))

    with patch("openforge.remove.get_project_dir", return_value=project_dir):
        result = runner.invoke(test_app, ["my-plugin"])
        assert result.exit_code == 0, result.output

    # Plugin canonical storage should be removed
    assert not plugin_dir.exists()

    # Claude adapter removals should have happened
    mcp_data = json.loads((project_dir / ".mcp.json").read_text())
    assert "test-server" not in mcp_data.get("mcpServers", {})
    assert not (claude_cmds / "deploy.md").exists()
    assert not (claude_hooks / "hooks.json").exists()


def test_remove_plugin_with_cursor_capabilities(tmp_path: Path) -> None:
    """Removing a plugin installed to cursor should remove cursor-specific artifacts."""
    test_app = _make_remove_app()

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create plugin canonical storage
    plugin_dir = project_dir / ".agents" / "plugins" / "my-plugin"
    plugin_dir.mkdir(parents=True)

    # MCP config
    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"cursor-srv": {"command": "run"}}})
    )

    # Commands
    cmds_dir = plugin_dir / "commands"
    cmds_dir.mkdir()
    (cmds_dir / "review.md").write_text("# Review")

    # Cursor-level mcp.json
    cursor_dir = project_dir / ".cursor"
    cursor_dir.mkdir()
    (cursor_dir / "mcp.json").write_text(
        json.dumps({"mcpServers": {"cursor-srv": {"command": "run"}, "other": {"command": "keep"}}})
    )

    # Cursor commands
    cursor_cmds = cursor_dir / "commands"
    cursor_cmds.mkdir()
    (cursor_cmds / "review.md").write_text("# Review")

    lock_path = project_dir / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.PLUGIN,
        source="acme/my-plugin",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/my-plugin",
        git_sha="abc123",
        skills=(),
        agents_installed=("cursor",),
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"my-plugin": entry}))

    with patch("openforge.remove.get_project_dir", return_value=project_dir):
        result = runner.invoke(test_app, ["my-plugin"])
        assert result.exit_code == 0, result.output

    # Cursor MCP should have "cursor-srv" removed but "other" kept
    mcp_data = json.loads((cursor_dir / "mcp.json").read_text())
    assert "cursor-srv" not in mcp_data["mcpServers"]
    assert "other" in mcp_data["mcpServers"]

    # Cursor commands removed
    assert not (cursor_cmds / "review.md").exists()


def test_remove_plugin_with_skills_and_agents(tmp_path: Path) -> None:
    """Removing a plugin that has skills installed to agents removes symlinks."""
    from openforge.agents.base import AgentConfig

    test_app = _make_remove_app()

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create skill canonical storage
    skill_dir = project_dir / ".agents" / "skills" / "helper"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test")

    # Create agent skill symlink
    agent_skills = tmp_path / ".test-agent" / "skills"
    agent_skills.mkdir(parents=True)
    (agent_skills / "helper").symlink_to(skill_dir)

    fake_agent = AgentConfig(
        name="test-agent",
        display_name="Test Agent",
        skills_dir=str(agent_skills),
        global_skills_dir=None,
        detect=lambda: True,
    )

    lock_path = project_dir / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.SKILL,
        source="acme/tools",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/tools",
        git_sha="abc123",
        skills=("helper",),
        agents_installed=("test-agent",),
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"acme/tools": entry}))

    with (
        patch("openforge.remove.get_project_dir", return_value=project_dir),
        patch("openforge.remove.get_agent", return_value=fake_agent),
    ):
        result = runner.invoke(test_app, ["acme/tools"])
        assert result.exit_code == 0, result.output

    # Agent symlink should be removed
    assert not (agent_skills / "helper").exists()
    # Canonical storage should be removed
    assert not skill_dir.exists()


def test_remove_plugin_with_multiple_skills(tmp_path: Path) -> None:
    """Removing an entry with multiple skills removes all canonical skill dirs."""
    test_app = _make_remove_app()

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    for skill_name in ("lint", "format", "test"):
        sd = project_dir / ".agents" / "skills" / skill_name
        sd.mkdir(parents=True)
        (sd / "SKILL.md").write_text("test")

    lock_path = project_dir / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.SKILL,
        source="acme/tools",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/tools",
        git_sha="abc123",
        skills=("lint", "format", "test"),
        agents_installed=(),
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"acme/tools": entry}))

    with patch("openforge.remove.get_project_dir", return_value=project_dir):
        result = runner.invoke(test_app, ["acme/tools"])
        assert result.exit_code == 0, result.output

    for skill_name in ("lint", "format", "test"):
        assert not (project_dir / ".agents" / "skills" / skill_name).exists()
