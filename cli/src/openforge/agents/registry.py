# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import shutil
from collections.abc import Sequence
from pathlib import Path

from openforge.agents.base import AgentConfig


def _dir_exists(name: str) -> bool:
    """Return True if a dot-directory exists in the cwd or the user home."""
    return Path(f".{name}").is_dir() or Path.home().joinpath(f".{name}").is_dir()


def _command_exists(cmd: str) -> bool:
    """Return True if *cmd* is on PATH."""
    return shutil.which(cmd) is not None


def _make_simple_agent(
    name: str,
    *,
    display_name: str | None = None,
    detect_command: str | None = None,
) -> AgentConfig:
    """Create a skills-only agent with the standard directory layout."""
    dname = display_name or name.replace("-", " ").title()
    skills_dir = f".{name}/skills"
    global_skills_dir = f"~/.{name}/skills"

    if detect_command is not None:
        cmd = detect_command

        def _detect() -> bool:
            return _dir_exists(name) or _command_exists(cmd)
    else:

        def _detect() -> bool:
            return _dir_exists(name)

    return AgentConfig(
        name=name,
        display_name=dname,
        skills_dir=skills_dir,
        global_skills_dir=global_skills_dir,
        detect=_detect,
    )


# ---------------------------------------------------------------------------
# Full-capabilities agents
# ---------------------------------------------------------------------------

_claude_code = AgentConfig(
    name="claude-code",
    display_name="Claude Code",
    skills_dir=".claude/skills",
    global_skills_dir="~/.claude/skills",
    detect=lambda: (
        Path(".claude").is_dir()
        or Path.home().joinpath(".claude").is_dir()
        or _command_exists("claude")
    ),
    capabilities=frozenset({"skills", "mcp", "commands", "hooks", "agents", "env"}),
)

_cursor = AgentConfig(
    name="cursor",
    display_name="Cursor",
    skills_dir=".cursor/skills",
    global_skills_dir="~/.cursor/skills",
    detect=lambda: _dir_exists("cursor"),
    capabilities=frozenset({"skills", "mcp", "commands"}),
)

_copilot = AgentConfig(
    name="copilot",
    display_name="GitHub Copilot",
    skills_dir=".github/copilot/skills",
    global_skills_dir="~/.github/copilot/skills",
    detect=lambda: (
        Path(".github/copilot").is_dir() or Path.home().joinpath(".github/copilot").is_dir()
    ),
)

# ---------------------------------------------------------------------------
# Skills-only agents (48)
# ---------------------------------------------------------------------------

_SIMPLE_AGENTS: list[AgentConfig] = [
    _make_simple_agent("windsurf"),
    _make_simple_agent("gemini-cli", display_name="Gemini CLI", detect_command="gemini"),
    _make_simple_agent("codex"),
    _make_simple_agent("opencode", display_name="OpenCode"),
    _make_simple_agent("aider", detect_command="aider"),
    _make_simple_agent("cline"),
    _make_simple_agent("roo-code", display_name="Roo Code"),
    _make_simple_agent("continue"),
    _make_simple_agent("zed"),
    _make_simple_agent("void"),
    _make_simple_agent("amp"),
    _make_simple_agent("kilo"),
    _make_simple_agent("augment"),
    _make_simple_agent("cody"),
    _make_simple_agent("sourcegraph", display_name="Sourcegraph"),
    _make_simple_agent("tabnine", display_name="Tabnine"),
    _make_simple_agent("supermaven", display_name="Supermaven"),
    _make_simple_agent("double"),
    _make_simple_agent("replit", display_name="Replit"),
    _make_simple_agent("pieces"),
    _make_simple_agent("codium"),
    _make_simple_agent("qodo"),
    _make_simple_agent("codeium"),
    _make_simple_agent("blackbox", display_name="Blackbox"),
    _make_simple_agent("mentat"),
    _make_simple_agent("devin"),
    _make_simple_agent("sweep"),
    _make_simple_agent("grit"),
    _make_simple_agent("cosine"),
    _make_simple_agent("bloop"),
    _make_simple_agent("phind"),
    _make_simple_agent("refact"),
    _make_simple_agent("codestory", display_name="CodeStory"),
    _make_simple_agent("privy"),
    _make_simple_agent("plandex"),
    _make_simple_agent("gpt-pilot", display_name="GPT Pilot"),
    _make_simple_agent("smol-developer", display_name="Smol Developer"),
    _make_simple_agent("auto-gpt", display_name="Auto GPT"),
    _make_simple_agent("devika"),
    _make_simple_agent("swe-agent", display_name="SWE Agent"),
    _make_simple_agent("aide"),
    _make_simple_agent("goose"),
    _make_simple_agent("codespin", display_name="CodeSpin"),
    _make_simple_agent("rawdog"),
    _make_simple_agent("rift"),
    _make_simple_agent("junie"),
    _make_simple_agent("trae"),
    _make_simple_agent("cowork"),
    # Agents from skills CLI (vercel-labs/skills) not previously included
    _make_simple_agent("antigravity", display_name="Antigravity"),
    _make_simple_agent("openclaw", display_name="OpenClaw"),
    _make_simple_agent("codebuddy", display_name="CodeBuddy"),
    _make_simple_agent("command-code", display_name="Command Code"),
    _make_simple_agent("cortex", display_name="Cortex Code"),
    _make_simple_agent("crush"),
    _make_simple_agent("droid"),
    _make_simple_agent("github-copilot", display_name="GitHub Copilot"),
    _make_simple_agent("iflow-cli", display_name="iFlow CLI"),
    _make_simple_agent("kimi-cli", display_name="Kimi Code CLI"),
    _make_simple_agent("kiro-cli", display_name="Kiro CLI"),
    _make_simple_agent("kode"),
    _make_simple_agent("mcpjam", display_name="MCPJam"),
    _make_simple_agent("mistral-vibe", display_name="Mistral Vibe"),
    _make_simple_agent("mux"),
    _make_simple_agent("neovate"),
    _make_simple_agent("openhands", display_name="OpenHands"),
    _make_simple_agent("pi"),
    _make_simple_agent("pochi"),
    _make_simple_agent("adal", display_name="AdaL"),
    _make_simple_agent("qoder"),
    _make_simple_agent("qwen-code", display_name="Qwen Code"),
    _make_simple_agent("zencoder"),
    _make_simple_agent("trae-cn", display_name="Trae CN"),
]

# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

AGENTS: list[AgentConfig] = [_claude_code, _cursor, _copilot, *_SIMPLE_AGENTS]


_AGENTS_BY_NAME: dict[str, AgentConfig] = {a.name: a for a in AGENTS}


def get_agent(name: str) -> AgentConfig | None:
    """Look up an agent by name, returning ``None`` if not found."""
    return _AGENTS_BY_NAME.get(name)


_cached_agents: list[AgentConfig] | None = None


def detect_agents(
    agents: Sequence[AgentConfig] | None = None,
) -> list[AgentConfig]:
    """Return agents whose ``detect`` callable returns ``True``.

    Results are cached when using the default agent list.
    """
    global _cached_agents  # noqa: PLW0603
    if agents is None:
        if _cached_agents is not None:
            return _cached_agents
        _cached_agents = [a for a in AGENTS if a.detect()]
        return _cached_agents
    return [a for a in agents if a.detect()]


def clear_agent_cache() -> None:
    """Reset the ``detect_agents`` cache. Useful for testing."""
    global _cached_agents  # noqa: PLW0603
    _cached_agents = None
