from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

import typer

from openforge.types import Source, DetectedContent, ContentType, PluginInfo, SkillInfo


def _fake_content_root(source: Source, dest: Path) -> Path:
    return dest


def test_add_skill_from_github(tmp_path: Path) -> None:
    """Integration test: add a skill, verify it prints success."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.add.detect_agents", return_value=[]), \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        # Mock: GitHub provider fetches to a temp dir with a skill
        def fake_fetch(source: Source, dest: Path) -> str:
            skill_dir = dest / "skills" / "lint"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: lint\n---\n")
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        # Mock: content detection finds the skill
        mock_content.return_value = DetectedContent(
            content_type=ContentType.SKILL,
            skills=(SkillInfo(name="lint", path="skills/lint"),),
        )

        result = runner.invoke(test_app, ["acme/tools"])
        assert result.exit_code == 0, result.output
        assert "lint" in result.output


def test_add_with_specific_agent(tmp_path: Path) -> None:
    """Test --agent flag."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.add.install_to_all_agents", return_value=["cursor"]), \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        def fake_fetch(source: Source, dest: Path) -> str:
            skill_dir = dest / "skills" / "lint"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: lint\n---\n")
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        mock_content.return_value = DetectedContent(
            content_type=ContentType.SKILL,
            skills=(SkillInfo(name="lint", path="skills/lint"),),
        )

        result = runner.invoke(test_app, ["acme/tools", "--agent", "cursor"])
        assert result.exit_code == 0, result.output


def test_e2e_with_local_repo(tmp_path: Path, sample_skill_repo: Path) -> None:
    """Full flow: detect content, create canonical storage, write lock file."""
    from openforge.plugins import detect_content
    from openforge.installer import create_canonical_storage
    from openforge.lock import add_lock_entry, read_lock
    from openforge.types import LockEntry, SourceType

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    content = detect_content(sample_skill_repo)
    assert len(content.skills) == 3

    for skill in content.skills:
        source_dir = sample_skill_repo / "skills" / skill.name
        create_canonical_storage(
            source_dir=source_dir,
            project_dir=project_dir,
            name=skill.name,
            content_type=content.content_type,
            is_global=False,
        )

    # Verify canonical storage
    for name in ["lint", "format", "test"]:
        assert (project_dir / ".agents" / "skills" / name / "SKILL.md").exists()

    # Write and verify lock file
    lock_path = project_dir / ".openforge-lock.json"
    for skill in content.skills:
        add_lock_entry(lock_path, skill.name, LockEntry(
            type=content.content_type,
            source="acme/tools",
            source_type=SourceType.GITHUB,
            git_url="https://github.com/acme/tools",
            git_sha="abc123",
            skills=(skill.name,),
            agents_installed=(),
            installed_at="2026-03-06T12:00:00Z",
            updated_at="2026-03-06T12:00:00Z",
        ))

    lock = read_lock(lock_path)
    assert len(lock.entries) == 3


def test_add_symlinks_point_to_canonical_not_temp(tmp_path: Path) -> None:
    """After add, agent symlinks must point to .agents/skills/, not to temp dir."""
    from openforge.add import add_command
    from openforge.agents.base import AgentConfig

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    fake_agent = AgentConfig(
        name="test-agent",
        display_name="Test Agent",
        skills_dir=str(tmp_path / ".test-agent" / "skills"),
        global_skills_dir=None,
        detect=lambda: True,
        capabilities=frozenset({"skills"}),
    )

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.installer.detect_agents", return_value=[fake_agent]), \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        def fake_fetch(source: Source, dest: Path) -> str:
            skill_dir = dest / "skills" / "lint"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: lint\n---\n")
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        mock_content.return_value = DetectedContent(
            content_type=ContentType.SKILL,
            skills=(SkillInfo(name="lint", path="skills/lint"),),
        )

        result = runner.invoke(test_app, ["acme/tools"])
        assert result.exit_code == 0, result.output

    # The symlink in the agent dir must point to the canonical location
    agent_link = tmp_path / ".test-agent" / "skills" / "lint"
    assert agent_link.is_symlink()
    target = agent_link.resolve()
    canonical = tmp_path / ".agents" / "skills" / "lint"
    assert target == canonical.resolve(), f"Symlink points to {target}, expected {canonical.resolve()}"


def test_add_shows_friendly_error_on_clone_failure(tmp_path: Path) -> None:
    """When git clone fails (repo not found), show a friendly error, not a traceback."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        MockProvider.return_value.fetch.side_effect = subprocess.CalledProcessError(
            128, ["git", "clone"], stderr="fatal: repository not found"
        )

        result = runner.invoke(test_app, ["acme/nonexistent"])
        # Should NOT show a Python traceback
        assert "Traceback" not in result.output
        # Should show a user-friendly error message
        assert result.exit_code != 0
        output_lower = result.output.lower()
        assert "failed" in output_lower or "error" in output_lower or "could not" in output_lower


def _setup_plugin_repo(dest: Path) -> None:
    """Create a plugin repo structure with MCP, hooks, and commands at dest."""
    dest.mkdir(parents=True, exist_ok=True)

    plugin_dir = dest / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "danger-plugin", "description": "A plugin"})
    )

    # MCP servers
    (dest / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"evil-server": {"command": "node", "args": ["server.js"]}}})
    )

    # Hooks
    hooks_dir = dest / ".claude"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "hooks.json").write_text(
        json.dumps({
            "hooks": [
                {"event": "PreToolUse", "command": ".claude/hooks/check.sh"},
                {"event": "PostToolUse", "command": ".claude/hooks/format.sh"},
            ]
        })
    )

    # Commands
    commands_dir = dest / "commands"
    commands_dir.mkdir()
    (commands_dir / "review.md").write_text("# Review")
    (commands_dir / "deploy.md").write_text("# Deploy")

    # Skill
    skill_dir = dest / "skills" / "helper"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: helper\n---\n")


def _make_plugin_detected(has_mcp: bool = True, has_hooks: bool = True, has_commands: bool = True) -> DetectedContent:
    """Return a DetectedContent for a plugin with the specified capabilities."""
    plugin = PluginInfo(
        name="danger-plugin",
        description="A plugin",
        skills=(SkillInfo(name="helper", path="skills/helper"),),
        has_mcp=has_mcp,
        has_commands=has_commands,
        has_hooks=has_hooks,
    )
    return DetectedContent(
        content_type=ContentType.PLUGIN,
        plugin=plugin,
        plugins=(plugin,),
        skills=(SkillInfo(name="helper", path="skills/helper"),),
    )


def test_add_plugin_shows_confirmation_prompt(tmp_path: Path) -> None:
    """When a plugin has MCP/hooks/commands, user sees a confirmation prompt."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.add.detect_agents", return_value=[]), \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        def fake_fetch(source: Source, dest: Path) -> str:
            _setup_plugin_repo(dest)
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        mock_content.return_value = _make_plugin_detected()

        # Answer "y" to the confirmation prompt
        result = runner.invoke(test_app, ["acme/plugin"], input="y\n")
        assert result.exit_code == 0, result.output
        # Should display what will be installed
        assert "danger-plugin" in result.output
        assert "MCP Servers" in result.output
        assert "evil-server" in result.output
        assert "Hooks" in result.output
        assert "PreToolUse" in result.output
        assert "Commands" in result.output
        assert "review.md" in result.output
        assert "deploy.md" in result.output


def test_add_plugin_yes_flag_skips_confirmation(tmp_path: Path) -> None:
    """The --yes flag auto-confirms without prompting."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.add.detect_agents", return_value=[]), \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        def fake_fetch(source: Source, dest: Path) -> str:
            _setup_plugin_repo(dest)
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        mock_content.return_value = _make_plugin_detected()

        # No input needed with --yes
        result = runner.invoke(test_app, ["acme/plugin", "--yes"])
        assert result.exit_code == 0, result.output
        # Should still display capabilities
        assert "danger-plugin" in result.output
        assert "MCP Servers" in result.output
        # Should NOT show the confirmation prompt text in output since it was auto-confirmed
        assert "Install these plugin capabilities?" not in result.output


def test_add_plugin_decline_skips_capabilities_but_installs_skills(tmp_path: Path) -> None:
    """Declining the prompt skips MCP/hooks/commands but still installs skills."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.add.detect_agents", return_value=[]), \
         patch("openforge.add._install_plugin_capabilities") as mock_install_caps, \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        def fake_fetch(source: Source, dest: Path) -> str:
            _setup_plugin_repo(dest)
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        mock_content.return_value = _make_plugin_detected()

        # Answer "n" to decline
        result = runner.invoke(test_app, ["acme/plugin"], input="n\n")
        assert result.exit_code == 0, result.output
        # Plugin capabilities should NOT be installed
        mock_install_caps.assert_not_called()
        # Should show skip message
        assert "Skipped" in result.output
        # Skills should still be installed (skill appears in summary table)
        assert "helper" in result.output


def test_add_plugin_agent_filter_applied_to_capabilities(tmp_path: Path) -> None:
    """When --agent is specified, _install_plugin_capabilities must only target that agent."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.add.install_to_all_agents", return_value=["cursor"]), \
         patch("openforge.add._install_plugin_capabilities") as mock_install_caps, \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        def fake_fetch(source: Source, dest: Path) -> str:
            _setup_plugin_repo(dest)
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        mock_content.return_value = _make_plugin_detected()

        result = runner.invoke(test_app, ["acme/plugin", "--agent", "cursor", "--yes"])
        assert result.exit_code == 0, result.output
        # _install_plugin_capabilities must receive the target_agent argument
        mock_install_caps.assert_called_once()
        call_kwargs = mock_install_caps.call_args
        # The function should receive the agent filter
        assert call_kwargs is not None
        # Check that target_agent="cursor" was passed
        if call_kwargs.kwargs:
            assert call_kwargs.kwargs.get("target_agent") == "cursor"
        else:
            # positional args: plugin, plugin_dir, project_dir, target_agent
            assert len(call_kwargs.args) >= 4
            assert call_kwargs.args[3] == "cursor"


def test_add_plugin_no_capabilities_skips_confirmation(tmp_path: Path) -> None:
    """A plugin with no MCP/hooks/commands does not prompt for confirmation."""
    from openforge.add import add_command

    test_app = typer.Typer()
    test_app.command("add")(add_command)
    runner = CliRunner()

    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_content") as mock_content, \
         patch("openforge.add.detect_agents", return_value=[]), \
         patch("openforge.add.get_project_dir", return_value=tmp_path), \
         patch("openforge.add.send_event"):

        def fake_fetch(source: Source, dest: Path) -> str:
            dest.mkdir(parents=True, exist_ok=True)
            plugin_dir = dest / ".claude-plugin"
            plugin_dir.mkdir()
            (plugin_dir / "plugin.json").write_text(
                json.dumps({"name": "safe-plugin", "description": "No caps"})
            )
            skill_dir = dest / "skills" / "helper"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: helper\n---\n")
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch
        MockProvider.return_value.content_root.side_effect = _fake_content_root

        safe_plugin = PluginInfo(
            name="safe-plugin",
            description="No caps",
            skills=(SkillInfo(name="helper", path="skills/helper"),),
            has_mcp=False,
            has_commands=False,
            has_hooks=False,
        )
        mock_content.return_value = DetectedContent(
            content_type=ContentType.PLUGIN,
            plugin=safe_plugin,
            plugins=(safe_plugin,),
            skills=(SkillInfo(name="helper", path="skills/helper"),),
        )

        # No input provided -- should not prompt
        result = runner.invoke(test_app, ["acme/safe-plugin"])
        assert result.exit_code == 0, result.output
        assert "Install these plugin capabilities?" not in result.output
