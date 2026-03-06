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
    detect=lambda: Path(".claude").is_dir()
    or Path.home().joinpath(".claude").is_dir()
    or _command_exists("claude"),
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

# ---------------------------------------------------------------------------
# Skills-only agents (49)
# ---------------------------------------------------------------------------

_SIMPLE_AGENTS: list[AgentConfig] = [
    _make_simple_agent("windsurf"),
    _make_simple_agent(
        "copilot",
        display_name="GitHub Copilot",
    ),
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
]

# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

AGENTS: list[AgentConfig] = [_claude_code, _cursor, *_SIMPLE_AGENTS]

# Copilot uses a non-standard skills_dir; patch it after construction.
# The helper builds `.copilot/skills` but the real path is `.github/copilot/skills`.
_copilot_idx = next(i for i, a in enumerate(AGENTS) if a.name == "copilot")
AGENTS[_copilot_idx] = AgentConfig(
    name="copilot",
    display_name="GitHub Copilot",
    skills_dir=".github/copilot/skills",
    global_skills_dir="~/.github/copilot/skills",
    detect=lambda: Path(".github/copilot").is_dir()
    or Path.home().joinpath(".github/copilot").is_dir(),
)


def get_agent(name: str) -> AgentConfig | None:
    """Look up an agent by name, returning ``None`` if not found."""
    for agent in AGENTS:
        if agent.name == name:
            return agent
    return None


def detect_agents(
    agents: Sequence[AgentConfig] | None = None,
) -> list[AgentConfig]:
    """Return agents whose ``detect`` callable returns ``True``."""
    candidates = agents if agents is not None else AGENTS
    return [a for a in candidates if a.detect()]
