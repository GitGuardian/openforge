# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from openforge.agents.base import AgentConfig
from openforge.agents.registry import AGENTS, detect_agents, get_agent


def test_agents_list_has_75_agents() -> None:
    assert len(AGENTS) == 75


def test_claude_code_has_all_capabilities() -> None:
    agent = get_agent("claude-code")
    assert agent is not None
    assert "skills" in agent.capabilities
    assert "mcp" in agent.capabilities
    assert "commands" in agent.capabilities
    assert "hooks" in agent.capabilities


def test_cursor_has_skills_mcp_commands() -> None:
    agent = get_agent("cursor")
    assert agent is not None
    assert agent.capabilities == frozenset({"skills", "mcp", "commands"})


def test_all_agents_have_skills() -> None:
    for agent in AGENTS:
        assert "skills" in agent.capabilities, f"{agent.name} missing skills capability"


def test_detect_agents_returns_installed() -> None:
    fake = AgentConfig(
        name="fake-agent",
        display_name="Fake Agent",
        skills_dir=".fake/skills",
        global_skills_dir=None,
        detect=lambda: True,
        capabilities=frozenset({"skills"}),
    )
    detected = detect_agents(agents=[fake])
    assert len(detected) == 1
    assert detected[0].name == "fake-agent"


def test_detect_agents_excludes_not_installed() -> None:
    fake = AgentConfig(
        name="missing-agent",
        display_name="Missing",
        skills_dir=".missing/skills",
        global_skills_dir=None,
        detect=lambda: False,
        capabilities=frozenset({"skills"}),
    )
    detected = detect_agents(agents=[fake])
    assert len(detected) == 0


def test_get_agent_returns_none_for_unknown() -> None:
    assert get_agent("nonexistent-agent") is None


def test_all_agent_names_are_unique() -> None:
    names = [a.name for a in AGENTS]
    assert len(names) == len(set(names))


def test_skills_cli_agents_present() -> None:
    """Agents from vercel-labs/skills should all be present in openforge."""
    skills_agents = [
        "antigravity",
        "openclaw",
        "codebuddy",
        "command-code",
        "cortex",
        "crush",
        "droid",
        "github-copilot",
        "iflow-cli",
        "kimi-cli",
        "kiro-cli",
        "kode",
        "mcpjam",
        "mistral-vibe",
        "mux",
        "neovate",
        "openhands",
        "pi",
        "pochi",
        "adal",
        "qoder",
        "qwen-code",
        "zencoder",
        "trae-cn",
    ]
    for name in skills_agents:
        assert get_agent(name) is not None, f"Missing agent from skills CLI: {name}"
