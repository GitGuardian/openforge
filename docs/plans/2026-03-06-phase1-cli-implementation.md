# Phase 1: CLI MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a working CLI (`uvx openforge`) that installs plugins and skills from GitHub repos across all 51 detected AI agents.

**Architecture:** Three-layer design — commands (Typer CLI), providers (GitHub content fetching), agents (data-driven registry with capability-based installation). Core install flow: parse source → fetch content → detect type → store canonically → symlink to agents → write lock file → fire telemetry.

**Tech Stack:** Python 3.10+, Typer, httpx, Rich, PyYAML, tomli/tomli-w, pyright strict

---

### Task 1: Types and shared data models

**Files:**
- Create: `cli/src/openforge/types.py`
- Test: `cli/tests/test_types.py` (light — mostly dataclass construction)

**Step 1: Write the types module**

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class ContentType(Enum):
    PLUGIN = "plugin"
    SKILL = "skill"


class SourceType(Enum):
    GITHUB = "github"


@dataclass(frozen=True)
class Source:
    """Parsed source reference (e.g. owner/repo@skill-name)."""
    owner: str
    repo: str
    skill_name: str | None = None
    subdir: str | None = None
    ref: str | None = None  # branch/tag

    @property
    def shorthand(self) -> str:
        s = f"{self.owner}/{self.repo}"
        if self.skill_name:
            s += f"@{self.skill_name}"
        return s

    @property
    def git_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


@dataclass(frozen=True)
class SkillInfo:
    """Parsed skill metadata from SKILL.md frontmatter."""
    name: str
    description: str = ""
    tags: tuple[str, ...] = ()
    path: str = ""  # relative path within the source


@dataclass(frozen=True)
class PluginInfo:
    """Parsed plugin metadata from plugin.json."""
    name: str
    description: str = ""
    skills: tuple[SkillInfo, ...] = ()
    has_mcp: bool = False
    has_commands: bool = False
    has_hooks: bool = False
    has_agents: bool = False
    has_env: bool = False


@dataclass(frozen=True)
class DetectedContent:
    """What the CLI found after scanning a fetched repo."""
    content_type: ContentType
    plugin: PluginInfo | None = None
    skills: tuple[SkillInfo, ...] = ()


@dataclass
class LockEntry:
    """One entry in the lock file."""
    type: ContentType
    source: str
    source_type: SourceType
    git_url: str
    git_sha: str
    skills: list[str]
    agents_installed: list[str]
    installed_at: str
    updated_at: str


@dataclass
class LockFile:
    """The full .openforge-lock.json contents."""
    version: int = 1
    entries: dict[str, LockEntry] = field(default_factory=dict)
```

**Step 2: Write a basic test to verify construction**

```python
from __future__ import annotations

from openforge.types import Source, ContentType, SkillInfo, PluginInfo, DetectedContent, LockEntry, LockFile, SourceType


def test_source_shorthand() -> None:
    src = Source(owner="acme", repo="tools")
    assert src.shorthand == "acme/tools"
    assert src.git_url == "https://github.com/acme/tools"


def test_source_shorthand_with_skill() -> None:
    src = Source(owner="acme", repo="tools", skill_name="lint")
    assert src.shorthand == "acme/tools@lint"


def test_detected_content_skill() -> None:
    skill = SkillInfo(name="lint", description="Lint code", path="skills/lint")
    content = DetectedContent(content_type=ContentType.SKILL, skills=(skill,))
    assert content.content_type == ContentType.SKILL
    assert len(content.skills) == 1


def test_lock_file_defaults() -> None:
    lock = LockFile()
    assert lock.version == 1
    assert lock.entries == {}
```

**Step 3: Run tests**

Run: `cd cli && uv run pytest tests/test_types.py -v`
Expected: PASS

**Step 4: Run pyright**

Run: `cd cli && uv run pyright src/openforge/types.py`
Expected: 0 errors

**Step 5: Commit**

```bash
git add cli/src/openforge/types.py cli/tests/test_types.py
git commit -m "feat(cli): add shared types and data models"
```

---

### Task 2: Source parser

**Files:**
- Create: `cli/src/openforge/providers/source_parser.py`
- Test: `cli/tests/test_source_parser.py`

**Step 1: Write the failing tests**

```python
from __future__ import annotations

import pytest
from openforge.providers.source_parser import parse_source
from openforge.types import Source


def test_parse_owner_repo() -> None:
    result = parse_source("acme/tools")
    assert result == Source(owner="acme", repo="tools")


def test_parse_owner_repo_at_skill() -> None:
    result = parse_source("acme/tools@lint")
    assert result == Source(owner="acme", repo="tools", skill_name="lint")


def test_parse_owner_repo_subdir() -> None:
    result = parse_source("acme/tools/skills/lint")
    assert result == Source(owner="acme", repo="tools", subdir="skills/lint")


def test_parse_github_url() -> None:
    result = parse_source("https://github.com/acme/tools")
    assert result == Source(owner="acme", repo="tools")


def test_parse_github_url_with_tree_path() -> None:
    result = parse_source("https://github.com/acme/tools/tree/main/skills/foo")
    assert result == Source(owner="acme", repo="tools", ref="main", subdir="skills/foo")


def test_parse_github_url_dot_git_suffix() -> None:
    result = parse_source("https://github.com/acme/tools.git")
    assert result == Source(owner="acme", repo="tools")


def test_parse_empty_raises() -> None:
    with pytest.raises(ValueError, match="empty"):
        parse_source("")


def test_parse_invalid_raises() -> None:
    with pytest.raises(ValueError, match="Invalid source"):
        parse_source("just-a-word")
```

**Step 2: Run tests to verify they fail**

Run: `cd cli && uv run pytest tests/test_source_parser.py -v`
Expected: FAIL (module not found)

**Step 3: Implement source parser**

```python
from __future__ import annotations

import re
from urllib.parse import urlparse

from openforge.types import Source


_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?(?:/tree/(?P<ref>[^/]+)(?:/(?P<subdir>.+))?)?/?$"
)

_SHORTHAND_RE = re.compile(
    r"^(?P<owner>[^/@]+)/(?P<repo>[^/@]+)(?:@(?P<skill>[^/]+))?(?:/(?P<subdir>.+))?$"
)


def parse_source(raw: str) -> Source:
    """Parse a source string into a Source object.

    Supports:
      - owner/repo
      - owner/repo@skill-name
      - owner/repo/path/to/subdir
      - https://github.com/owner/repo
      - https://github.com/owner/repo/tree/ref/path
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("Source cannot be empty")

    # Try GitHub URL first
    if raw.startswith(("http://", "https://")):
        m = _GITHUB_URL_RE.match(raw)
        if not m:
            raise ValueError(f"Invalid source URL: {raw}")
        return Source(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref"),
            subdir=m.group("subdir"),
        )

    # Try shorthand
    m = _SHORTHAND_RE.match(raw)
    if not m:
        raise ValueError(f"Invalid source: {raw}")

    return Source(
        owner=m.group("owner"),
        repo=m.group("repo"),
        skill_name=m.group("skill"),
        subdir=m.group("subdir"),
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd cli && uv run pytest tests/test_source_parser.py -v`
Expected: PASS

**Step 5: Run pyright**

Run: `cd cli && uv run pyright src/openforge/providers/source_parser.py`
Expected: 0 errors

**Step 6: Commit**

```bash
git add cli/src/openforge/providers/source_parser.py cli/tests/test_source_parser.py
git commit -m "feat(cli): add source parser for owner/repo@skill and GitHub URLs"
```

---

### Task 3: Config file (TOML read/write with precedence)

**Files:**
- Create: `cli/src/openforge/config_file.py`
- Test: `cli/tests/test_config_file.py`

**Step 1: Write failing tests**

```python
from __future__ import annotations

import os
from pathlib import Path

from openforge.config_file import load_config, get_config_value, set_config_value, ConfigValue


def test_load_defaults(tmp_path: Path) -> None:
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.forge_url == "https://openforge.gitguardian.com"
    assert config.telemetry_enabled is True


def test_user_config_overrides_defaults(tmp_path: Path) -> None:
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "config.toml").write_text('[forge]\nurl = "https://forge.acme.com"\n')
    config = load_config(project_dir=tmp_path, user_config_dir=user_dir)
    assert config.forge_url == "https://forge.acme.com"


def test_project_config_overrides_user(tmp_path: Path) -> None:
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "config.toml").write_text('[forge]\nurl = "https://user.com"\n')
    (tmp_path / ".openforge.toml").write_text('[forge]\nurl = "https://project.com"\n')
    config = load_config(project_dir=tmp_path, user_config_dir=user_dir)
    assert config.forge_url == "https://project.com"


def test_env_var_overrides_all(tmp_path: Path, monkeypatch: object) -> None:
    (tmp_path / ".openforge.toml").write_text('[forge]\nurl = "https://project.com"\n')
    # monkeypatch is pytest.MonkeyPatch but we keep typing simple
    monkeypatch.setenv("OPENFORGE_FORGE_URL", "https://env.com")  # type: ignore[union-attr]
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.forge_url == "https://env.com"


def test_do_not_track_disables_telemetry(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("DO_NOT_TRACK", "1")  # type: ignore[union-attr]
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.telemetry_enabled is False


def test_get_config_value(tmp_path: Path) -> None:
    (tmp_path / ".openforge.toml").write_text('[forge]\nurl = "https://project.com"\n')
    val = get_config_value("forge.url", project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert val.value == "https://project.com"
    assert val.source == "project"


def test_set_config_value(tmp_path: Path) -> None:
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    set_config_value("forge.url", "https://new.com", user_config_dir=user_dir)
    content = (user_dir / "config.toml").read_text()
    assert "https://new.com" in content
```

**Step 2: Run tests to verify failure**

Run: `cd cli && uv run pytest tests/test_config_file.py -v`
Expected: FAIL

**Step 3: Implement config_file.py**

Implement `load_config()` that reads TOML files with `tomli` (or `tomllib` on 3.11+), merges them in precedence order, checks env vars. Implement `get_config_value()` and `set_config_value()` using `tomli_w`. Create a `Config` dataclass and `ConfigValue` dataclass.

Key implementation details:
- Use `tomllib` (stdlib 3.11+) with fallback to `tomli` for 3.10
- `Config` dataclass with `forge_url: str`, `telemetry_enabled: bool`
- `ConfigValue` dataclass with `value: str`, `source: str` (one of "default", "user", "project", "env")
- CI env var detection: check `CI`, `GITHUB_ACTIONS`, `GITLAB_CI`, `JENKINS_URL`, `CIRCLECI`, `TRAVIS`

**Step 4: Run tests**

Run: `cd cli && uv run pytest tests/test_config_file.py -v`
Expected: PASS

**Step 5: Run pyright**

Run: `cd cli && uv run pyright src/openforge/config_file.py`
Expected: 0 errors

**Step 6: Commit**

```bash
git add cli/src/openforge/config_file.py cli/tests/test_config_file.py
git commit -m "feat(cli): add config file support with TOML read/write and precedence"
```

---

### Task 4: Lock file read/write

**Files:**
- Create: `cli/src/openforge/lock.py`
- Test: `cli/tests/test_lock.py`

**Step 1: Write failing tests**

```python
from __future__ import annotations

import json
from pathlib import Path

from openforge.lock import read_lock, write_lock, add_lock_entry, remove_lock_entry
from openforge.types import LockFile, LockEntry, ContentType, SourceType


def test_read_lock_missing_file(tmp_path: Path) -> None:
    lock = read_lock(tmp_path / ".openforge-lock.json")
    assert lock.version == 1
    assert lock.entries == {}


def test_write_and_read_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.SKILL,
        source="acme/tools@lint",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/tools",
        git_sha="abc123",
        skills=["lint"],
        agents_installed=["claude-code"],
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    lock = LockFile(entries={"lint": entry})
    write_lock(lock_path, lock)

    loaded = read_lock(lock_path)
    assert "lint" in loaded.entries
    assert loaded.entries["lint"].git_sha == "abc123"
    assert loaded.entries["lint"].type == ContentType.SKILL


def test_add_lock_entry(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.PLUGIN,
        source="acme/plugin",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/plugin",
        git_sha="def456",
        skills=["skill-a", "skill-b"],
        agents_installed=["claude-code", "cursor"],
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    add_lock_entry(lock_path, "my-plugin", entry)

    lock = read_lock(lock_path)
    assert "my-plugin" in lock.entries


def test_remove_lock_entry(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.SKILL,
        source="acme/tools@lint",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/tools",
        git_sha="abc123",
        skills=["lint"],
        agents_installed=["claude-code"],
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    lock = LockFile(entries={"lint": entry})
    write_lock(lock_path, lock)

    remove_lock_entry(lock_path, "lint")
    lock = read_lock(lock_path)
    assert "lint" not in lock.entries


def test_lock_file_json_format(tmp_path: Path) -> None:
    """Verify the JSON output matches the spec format."""
    lock_path = tmp_path / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.PLUGIN,
        source="acme/plugin",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/plugin",
        git_sha="abc123",
        skills=["skill-a"],
        agents_installed=["claude-code"],
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"my-plugin": entry}))

    raw = json.loads(lock_path.read_text())
    assert raw["version"] == 1
    assert raw["entries"]["my-plugin"]["type"] == "plugin"
    assert raw["entries"]["my-plugin"]["source_type"] == "github"
```

**Step 2: Run tests to verify failure**

Run: `cd cli && uv run pytest tests/test_lock.py -v`
Expected: FAIL

**Step 3: Implement lock.py**

JSON serialisation/deserialisation of LockFile. Use `json` stdlib. Serialize enums as `.value`. Deserialize by mapping strings back to enums.

**Step 4: Run tests**

Run: `cd cli && uv run pytest tests/test_lock.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/src/openforge/lock.py cli/tests/test_lock.py
git commit -m "feat(cli): add lock file read/write with JSON serialisation"
```

---

### Task 5: SKILL.md parsing

**Files:**
- Create: `cli/src/openforge/skills.py`
- Test: `cli/tests/test_skills.py` (new file — rename from conftest usage)

**Step 1: Write failing tests**

```python
from __future__ import annotations

from pathlib import Path

from openforge.skills import parse_skill_md, find_skills_in_dir
from openforge.types import SkillInfo


def test_parse_skill_md_with_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "lint"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: lint\ndescription: Lint your code\ntags:\n  - quality\n  - python\n---\n\n# Lint Skill\n\nLints things.\n"
    )
    skill = parse_skill_md(skill_dir / "SKILL.md")
    assert skill.name == "lint"
    assert skill.description == "Lint your code"
    assert skill.tags == ("quality", "python")


def test_parse_skill_md_no_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "simple"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Simple Skill\n\nDoes stuff.\n")
    skill = parse_skill_md(skill_dir / "SKILL.md")
    assert skill.name == "simple"  # inferred from directory name
    assert skill.description == ""


def test_find_skills_root_skill_md(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text("---\nname: root-skill\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 1
    assert skills[0].name == "root-skill"


def test_find_skills_skills_directory(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    for name in ["lint", "format"]:
        d = skills_dir / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 2
    names = {s.name for s in skills}
    assert names == {"lint", "format"}


def test_find_skills_curated_dir(tmp_path: Path) -> None:
    curated = tmp_path / "skills" / ".curated"
    curated.mkdir(parents=True)
    skill_dir = curated / "good-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: good-skill\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 1


def test_find_skills_agent_specific_dir(tmp_path: Path) -> None:
    agent_dir = tmp_path / ".claude" / "skills" / "my-skill"
    agent_dir.mkdir(parents=True)
    (agent_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 1
```

**Step 2: Run tests to verify failure**

Run: `cd cli && uv run pytest tests/test_skills.py -v`
Expected: FAIL

**Step 3: Implement skills.py**

Parse YAML frontmatter from SKILL.md files using PyYAML. Implement `find_skills_in_dir()` with the priority order from the design doc: root SKILL.md → skills/ dir → curated/experimental/system → agent-specific dirs → recursive fallback.

**Step 4: Run tests**

Run: `cd cli && uv run pytest tests/test_skills.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/src/openforge/skills.py cli/tests/test_skills.py
git commit -m "feat(cli): add SKILL.md parsing with frontmatter and directory scanning"
```

---

### Task 6: Plugin parsing (plugin.json + marketplace.json)

**Files:**
- Create: `cli/src/openforge/plugins.py`
- Test: `cli/tests/test_plugins.py` (new file)

**Step 1: Write failing tests**

```python
from __future__ import annotations

import json
from pathlib import Path

from openforge.plugins import parse_plugin, parse_marketplace, detect_content
from openforge.types import ContentType


def test_parse_plugin_json(tmp_path: Path) -> None:
    plugin_dir = tmp_path / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(json.dumps({
        "name": "my-plugin",
        "description": "A test plugin",
    }))
    # Create skills inside the plugin
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


def test_detect_content_skill(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills" / "lint"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: lint\n---\n")
    content = detect_content(tmp_path)
    assert content.content_type == ContentType.SKILL
    assert len(content.skills) == 1
```

**Step 2: Run tests to verify failure**

Run: `cd cli && uv run pytest tests/test_plugins.py -v`
Expected: FAIL

**Step 3: Implement plugins.py**

Parse `plugin.json`, detect MCP/commands/hooks/agents/env by checking for their files. Parse `marketplace.json` for multi-plugin repos. Implement `detect_content()` that decides plugin vs skill based on presence of `.claude-plugin/plugin.json` or `marketplace.json`.

**Step 4: Run tests**

Run: `cd cli && uv run pytest tests/test_plugins.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/src/openforge/plugins.py cli/tests/test_plugins.py
git commit -m "feat(cli): add plugin.json and marketplace.json parsing with content detection"
```

---

### Task 7: Agent registry (data-driven, all 51 agents)

**Files:**
- Create: `cli/src/openforge/agents/base.py`
- Create: `cli/src/openforge/agents/registry.py`
- Test: `cli/tests/test_agents.py`

**Step 1: Write failing tests**

```python
from __future__ import annotations

from pathlib import Path

from openforge.agents.base import AgentConfig
from openforge.agents.registry import AGENTS, get_agent, detect_agents


def test_agents_list_has_51_agents() -> None:
    assert len(AGENTS) == 51


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


def test_detect_agents_returns_installed(tmp_path: Path, monkeypatch: object) -> None:
    """Mock detection — just verify the function filters correctly."""
    # Create a fake agent that always detects as installed
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
```

**Step 2: Run tests to verify failure**

Run: `cd cli && uv run pytest tests/test_agents.py -v`
Expected: FAIL

**Step 3: Implement base.py with AgentConfig dataclass**

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AgentConfig:
    name: str
    display_name: str
    skills_dir: str
    global_skills_dir: str | None
    detect: Callable[[], bool]
    capabilities: frozenset[str] = frozenset({"skills"})
    show_in_list: bool = True
```

**Step 4: Implement registry.py with all 51 agents**

Port agent definitions from skills.sh source. Each agent gets a `detect()` function (check for config dirs/files on disk). Claude Code and Cursor get richer capabilities.

Reference for 51 agents: https://github.com/vercel-labs/skills — check their agent configs for names, skill dirs, and detection logic. Map each one to an `AgentConfig`.

Key agents to get right:
- `claude-code`: `.claude/skills`, detect via `.claude/` dir or `claude` binary
- `cursor`: `.cursor/skills`, detect via `.cursor/` dir
- `windsurf`: `.windsurf/skills`
- `copilot`: `.github/copilot/skills`
- `gemini-cli`: `.gemini/skills`
- `codex`: `.codex/skills`
- All others: follow skills.sh patterns

**Step 5: Run tests**

Run: `cd cli && uv run pytest tests/test_agents.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add cli/src/openforge/agents/base.py cli/src/openforge/agents/registry.py cli/tests/test_agents.py
git commit -m "feat(cli): add data-driven agent registry with all 51 agents"
```

---

### Task 8: GitHub provider (clone/fetch repos)

**Files:**
- Create: `cli/src/openforge/providers/base.py`
- Create: `cli/src/openforge/providers/github.py`
- Test: (integration-style tests in `cli/tests/test_add.py` later — for now just unit test the URL building)

**Step 1: Implement provider base protocol**

```python
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from openforge.types import Source


class Provider(Protocol):
    def fetch(self, source: Source, dest: Path) -> str:
        """Fetch content to dest directory. Return git SHA."""
        ...
```

**Step 2: Implement GitHub provider**

Uses `git clone --depth 1` via subprocess for public repos. Uses `GITHUB_TOKEN`/`GH_TOKEN` env var for private repos (sets in clone URL). Returns the HEAD SHA after clone.

If `source.subdir` is set, clone the full repo then return `dest / subdir` as the content root.

If `source.ref` is set, clone that specific ref.

Key implementation:
- `subprocess.run(["git", "clone", "--depth", "1", url, str(dest)], ...)`
- Get SHA: `subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"], ...)`
- Handle `source.ref` with `--branch`
- Handle auth token in URL: `https://{token}@github.com/...`

**Step 3: Run pyright**

Run: `cd cli && uv run pyright src/openforge/providers/`
Expected: 0 errors

**Step 4: Commit**

```bash
git add cli/src/openforge/providers/base.py cli/src/openforge/providers/github.py
git commit -m "feat(cli): add GitHub provider with git clone and auth token support"
```

---

### Task 9: Installer (core symlink/copy + agent dispatch)

**Files:**
- Create: `cli/src/openforge/installer.py`
- Test: `cli/tests/test_installer.py`

**Step 1: Write failing tests**

```python
from __future__ import annotations

import os
from pathlib import Path

from openforge.installer import (
    install_skills_to_agent,
    create_canonical_storage,
    remove_canonical_storage,
)
from openforge.agents.base import AgentConfig
from openforge.types import SkillInfo, ContentType


def _make_agent(tmp_path: Path) -> AgentConfig:
    skills_dir = tmp_path / ".test-agent" / "skills"
    return AgentConfig(
        name="test-agent",
        display_name="Test Agent",
        skills_dir=str(skills_dir),
        global_skills_dir=None,
        detect=lambda: True,
    )


def test_create_canonical_storage_skill(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "SKILL.md").write_text("---\nname: test\n---\n")

    dest = create_canonical_storage(
        source_dir=source_dir,
        project_dir=tmp_path / "project",
        name="test-skill",
        content_type=ContentType.SKILL,
        is_global=False,
    )
    assert dest.exists()
    assert (dest / "SKILL.md").exists()
    assert "skills" in str(dest)  # .agents/skills/test-skill/


def test_create_canonical_storage_plugin(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    plugin_dir = source_dir / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"name": "test"}')

    dest = create_canonical_storage(
        source_dir=source_dir,
        project_dir=tmp_path / "project",
        name="test-plugin",
        content_type=ContentType.PLUGIN,
        is_global=False,
    )
    assert dest.exists()
    assert "plugins" in str(dest)  # .agents/plugins/test-plugin/


def test_install_skills_to_agent_creates_symlinks(tmp_path: Path) -> None:
    # Setup canonical skill
    skill_dir = tmp_path / "project" / ".agents" / "skills" / "lint"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: lint\n---\n")

    agent = _make_agent(tmp_path)
    skills = [SkillInfo(name="lint", path=str(skill_dir))]

    install_skills_to_agent(
        agent=agent,
        skills=skills,
        project_dir=tmp_path / "project",
        is_global=False,
    )

    agent_skill = Path(agent.skills_dir) / "lint"
    assert agent_skill.is_symlink()
    assert agent_skill.resolve() == skill_dir.resolve()


def test_remove_canonical_storage(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    skill_dir = project_dir / ".agents" / "skills" / "test"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("test")

    remove_canonical_storage(project_dir=project_dir, name="test", content_type=ContentType.SKILL, is_global=False)
    assert not skill_dir.exists()
```

**Step 2: Run tests to verify failure**

Run: `cd cli && uv run pytest tests/test_installer.py -v`
Expected: FAIL

**Step 3: Implement installer.py**

Core functions:
- `create_canonical_storage()` — copy fetched content to `.agents/plugins/` or `.agents/skills/`
- `install_skills_to_agent()` — create symlinks from agent skills dir to canonical location
- `remove_skills_from_agent()` — remove symlinks
- `remove_canonical_storage()` — delete the canonical directory
- `install_to_all_agents()` — orchestrator that calls detect_agents, then installs to each

Symlink strategy: relative symlinks where possible (`os.path.relpath`), absolute as fallback. Copy fallback if symlink fails (Windows).

**Step 4: Run tests**

Run: `cd cli && uv run pytest tests/test_installer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/src/openforge/installer.py cli/tests/test_installer.py
git commit -m "feat(cli): add installer with symlink-based agent skill installation"
```

---

### Task 10: Claude Code adapter (MCP, commands, hooks)

**Files:**
- Create: `cli/src/openforge/agents/adapters/claude.py`
- Test: `cli/tests/test_adapters.py` (new file)

**Step 1: Write failing tests**

```python
from __future__ import annotations

import json
from pathlib import Path

from openforge.agents.adapters.claude import install_mcp_config, install_commands, install_hooks


def test_install_mcp_config(tmp_path: Path) -> None:
    # Source plugin has .mcp.json
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

    # Should merge into project's .mcp.json
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
```

**Step 2: Run tests to verify failure**

Run: `cd cli && uv run pytest tests/test_adapters.py -v`
Expected: FAIL

**Step 3: Implement Claude adapter**

Functions for each capability: `install_mcp_config()` (merge JSON), `install_commands()` (copy/symlink .md files), `install_hooks()` (copy hooks.json). Each reads from plugin dir and writes to project's `.claude/` structure.

**Step 4: Run tests**

Run: `cd cli && uv run pytest tests/test_adapters.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/src/openforge/agents/adapters/claude.py cli/tests/test_adapters.py
git commit -m "feat(cli): add Claude Code adapter for MCP, commands, and hooks"
```

---

### Task 11: Cursor adapter (MCP, commands)

**Files:**
- Modify: `cli/src/openforge/agents/adapters/cursor.py`
- Modify: `cli/tests/test_adapters.py` (add Cursor tests)

**Step 1: Write failing tests (append to test_adapters.py)**

```python
from openforge.agents.adapters.cursor import install_mcp_config as cursor_install_mcp


def test_cursor_install_mcp_config(tmp_path: Path) -> None:
    plugin_dir = tmp_path / "plugin"
    plugin_dir.mkdir()
    (plugin_dir / ".mcp.json").write_text(json.dumps({
        "mcpServers": {
            "my-server": {"command": "node", "args": ["server.js"]}
        }
    }))

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    cursor_install_mcp(plugin_dir=plugin_dir, project_dir=project_dir)

    # Cursor uses .cursor/mcp.json (slightly different format)
    mcp_path = project_dir / ".cursor" / "mcp.json"
    assert mcp_path.exists()
```

**Step 2: Implement Cursor adapter**

Cursor's MCP config goes to `.cursor/mcp.json`. Commands go to `.cursor/commands/`. Similar to Claude but different paths and potentially different config format.

**Step 3: Run tests**

Run: `cd cli && uv run pytest tests/test_adapters.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/src/openforge/agents/adapters/cursor.py cli/tests/test_adapters.py
git commit -m "feat(cli): add Cursor adapter for MCP and commands"
```

---

### Task 12: Telemetry (fire-and-forget)

**Files:**
- Create: `cli/src/openforge/telemetry.py`
- Test: (minimal — fire-and-forget is hard to unit test meaningfully)

**Step 1: Implement telemetry.py**

```python
from __future__ import annotations

import threading
from typing import Any

import httpx

from openforge.config_file import load_config


def _is_ci() -> bool:
    import os
    ci_vars = ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "CIRCLECI", "TRAVIS", "BUILDKITE")
    return any(os.environ.get(v) for v in ci_vars)


def send_event(event: str, data: dict[str, Any]) -> None:
    """Fire-and-forget telemetry event. Never raises, never blocks."""
    config = load_config()
    if not config.telemetry_enabled or _is_ci():
        return

    payload = {"event": event, **data}

    def _send() -> None:
        try:
            httpx.post(
                f"{config.forge_url}/api/telemetry",
                json=payload,
                timeout=5.0,
            )
        except Exception:
            pass  # Fire and forget

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
```

**Step 2: Run pyright**

Run: `cd cli && uv run pyright src/openforge/telemetry.py`
Expected: 0 errors

**Step 3: Commit**

```bash
git add cli/src/openforge/telemetry.py
git commit -m "feat(cli): add fire-and-forget telemetry with CI auto-disable"
```

---

### Task 13: `add` command

**Files:**
- Create: `cli/src/openforge/add.py`
- Test: `cli/tests/test_add.py`
- Modify: `cli/src/openforge/cli.py`

**Step 1: Write the integration test**

```python
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from openforge.cli import app
from openforge.types import Source


runner = CliRunner()


def test_add_skill_from_github(tmp_path: Path) -> None:
    """Integration test: add a skill, verify canonical storage + symlinks + lock file."""
    with patch("openforge.add.GitHubProvider") as MockProvider, \
         patch("openforge.add.detect_agents") as mock_detect, \
         patch("openforge.add.detect_content") as mock_content:

        # Mock: GitHub provider fetches to a temp dir with a skill
        def fake_fetch(source: Source, dest: Path) -> str:
            skill_dir = dest / "skills" / "lint"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text("---\nname: lint\n---\n")
            return "abc123"

        MockProvider.return_value.fetch.side_effect = fake_fetch

        # Mock: content detection finds the skill
        from openforge.types import DetectedContent, ContentType, SkillInfo
        mock_content.return_value = DetectedContent(
            content_type=ContentType.SKILL,
            skills=(SkillInfo(name="lint", path="skills/lint"),),
        )

        # Mock: no agents detected (simplify test)
        mock_detect.return_value = []

        result = runner.invoke(app, ["add", "acme/tools"], env={"HOME": str(tmp_path)})
        assert result.exit_code == 0
        assert "lint" in result.stdout
```

**Step 2: Implement add.py**

Orchestrates the full add flow:
1. Parse source (source_parser)
2. Create temp dir, fetch via GitHub provider
3. Detect content (plugins.detect_content)
4. Create canonical storage (installer)
5. Detect agents, install to each (installer)
6. For agents with capabilities beyond skills: dispatch to adapters
7. Write lock entry
8. Fire telemetry
9. Print Rich summary

**Step 3: Wire up cli.py**

```python
from __future__ import annotations

import typer

app = typer.Typer(name="openforge", help="Install and manage AI agent plugins and skills.")

# Import and register command modules
from openforge.add import add_command
from openforge.remove import remove_command
from openforge.list import list_command
from openforge.find import find_command
from openforge.config import config_app

app.command("add")(add_command)
app.command("remove")(remove_command)
app.command("list")(list_command)
app.command("find")(find_command)
app.add_typer(config_app, name="config")
```

**Step 4: Run tests**

Run: `cd cli && uv run pytest tests/test_add.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/src/openforge/add.py cli/src/openforge/cli.py cli/tests/test_add.py
git commit -m "feat(cli): implement add command with full install flow"
```

---

### Task 14: `remove` command

**Files:**
- Create: `cli/src/openforge/remove.py`
- Test: `cli/tests/test_remove.py`

**Step 1: Write failing test**

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from openforge.cli import app
from openforge.types import LockFile, LockEntry, ContentType, SourceType
from openforge.lock import write_lock

runner = CliRunner()


def test_remove_installed_skill(tmp_path: Path) -> None:
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
        skills=["lint"],
        agents_installed=[],
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"lint": entry}))

    with patch("openforge.remove.get_project_dir", return_value=project_dir):
        result = runner.invoke(app, ["remove", "lint"])
        assert result.exit_code == 0

    assert not skill_dir.exists()
```

**Step 2: Implement remove.py**

1. Read lock file, find entry by name
2. Remove symlinks from all agents that had it installed
3. Remove canonical storage
4. Remove lock entry
5. Fire telemetry
6. Print summary

**Step 3: Run tests**

Run: `cd cli && uv run pytest tests/test_remove.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/src/openforge/remove.py cli/tests/test_remove.py
git commit -m "feat(cli): implement remove command with symlink cleanup"
```

---

### Task 15: `list` command

**Files:**
- Create: `cli/src/openforge/list.py`
- Test: `cli/tests/test_list.py`

**Step 1: Write failing test**

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from openforge.cli import app
from openforge.types import LockFile, LockEntry, ContentType, SourceType
from openforge.lock import write_lock

runner = CliRunner()


def test_list_shows_installed(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    write_lock(lock_path, LockFile(entries={
        "lint": LockEntry(
            type=ContentType.SKILL,
            source="acme/tools@lint",
            source_type=SourceType.GITHUB,
            git_url="https://github.com/acme/tools",
            git_sha="abc123",
            skills=["lint"],
            agents_installed=["claude-code"],
            installed_at="2026-03-06T12:00:00Z",
            updated_at="2026-03-06T12:00:00Z",
        ),
    }))

    with patch("openforge.list.get_project_dir", return_value=tmp_path):
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "lint" in result.stdout
        assert "acme/tools" in result.stdout


def test_list_empty(tmp_path: Path) -> None:
    with patch("openforge.list.get_project_dir", return_value=tmp_path):
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No plugins or skills installed" in result.stdout
```

**Step 2: Implement list.py**

Read lock file, format as Rich table: Name | Type | Source | Skills | Agents. Support `--global` and `--agent` filter flags.

**Step 3: Run tests**

Run: `cd cli && uv run pytest tests/test_list.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/src/openforge/list.py cli/tests/test_list.py
git commit -m "feat(cli): implement list command with Rich table output"
```

---

### Task 16: `find` command

**Files:**
- Create: `cli/src/openforge/find.py`
- Test: `cli/tests/test_find.py`

**Step 1: Write failing test**

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from openforge.cli import app
from openforge.types import LockFile, LockEntry, ContentType, SourceType
from openforge.lock import write_lock

runner = CliRunner()


def test_find_by_name(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    write_lock(lock_path, LockFile(entries={
        "lint": LockEntry(
            type=ContentType.SKILL,
            source="acme/tools@lint",
            source_type=SourceType.GITHUB,
            git_url="https://github.com/acme/tools",
            git_sha="abc123",
            skills=["lint"],
            agents_installed=["claude-code"],
            installed_at="2026-03-06T12:00:00Z",
            updated_at="2026-03-06T12:00:00Z",
        ),
        "format": LockEntry(
            type=ContentType.SKILL,
            source="acme/tools@format",
            source_type=SourceType.GITHUB,
            git_url="https://github.com/acme/tools",
            git_sha="abc123",
            skills=["format"],
            agents_installed=["claude-code"],
            installed_at="2026-03-06T12:00:00Z",
            updated_at="2026-03-06T12:00:00Z",
        ),
    }))

    with patch("openforge.find.get_project_dir", return_value=tmp_path):
        result = runner.invoke(app, ["find", "lint"])
        assert result.exit_code == 0
        assert "lint" in result.stdout
        # "format" should not appear when searching for "lint"


def test_find_no_results(tmp_path: Path) -> None:
    with patch("openforge.find.get_project_dir", return_value=tmp_path):
        result = runner.invoke(app, ["find", "nonexistent"])
        assert result.exit_code == 0
        assert "No results" in result.stdout
```

**Step 2: Implement find.py**

Search locally installed skills by name (substring match), description, and tags. Support `--tag` filter. Display results as Rich table. Fire telemetry event.

**Step 3: Run tests**

Run: `cd cli && uv run pytest tests/test_find.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/src/openforge/find.py cli/tests/test_find.py
git commit -m "feat(cli): implement find command with local search"
```

---

### Task 17: `config` command

**Files:**
- Create: `cli/src/openforge/config.py`
- Test: `cli/tests/test_config.py` (new file)

**Step 1: Write failing test**

```python
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from openforge.cli import app

runner = CliRunner()


def test_config_list(tmp_path: Path) -> None:
    with patch("openforge.config.get_user_config_dir", return_value=tmp_path / "user"), \
         patch("openforge.config.get_project_dir", return_value=tmp_path):
        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        assert "forge.url" in result.stdout


def test_config_get(tmp_path: Path) -> None:
    with patch("openforge.config.get_user_config_dir", return_value=tmp_path / "user"), \
         patch("openforge.config.get_project_dir", return_value=tmp_path):
        result = runner.invoke(app, ["config", "get", "forge.url"])
        assert result.exit_code == 0
        assert "openforge.gitguardian.com" in result.stdout


def test_config_set(tmp_path: Path) -> None:
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    with patch("openforge.config.get_user_config_dir", return_value=user_dir):
        result = runner.invoke(app, ["config", "set", "forge.url", "https://new.com"])
        assert result.exit_code == 0

    content = (user_dir / "config.toml").read_text()
    assert "https://new.com" in content
```

**Step 2: Implement config.py**

Typer sub-app with `set`, `get`, `list` subcommands. Uses `config_file.py` for read/write. Shows resolved value + source on `get`.

**Step 3: Run tests**

Run: `cd cli && uv run pytest tests/test_config.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/src/openforge/config.py cli/tests/test_config.py
git commit -m "feat(cli): implement config command with get/set/list"
```

---

### Task 18: Test fixtures and conftest

**Files:**
- Create: `cli/tests/conftest.py`

**Step 1: Implement shared fixtures**

```python
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A temporary project directory with .agents/ structure."""
    agents = tmp_path / ".agents"
    (agents / "plugins").mkdir(parents=True)
    (agents / "skills").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def sample_skill_repo(tmp_path: Path) -> Path:
    """A temporary directory mimicking a GitHub repo with skills."""
    repo = tmp_path / "repo"
    skills = repo / "skills"
    for name in ["lint", "format", "test"]:
        skill_dir = skills / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name.title()} your code\ntags:\n  - quality\n---\n"
        )
    return repo


@pytest.fixture
def sample_plugin_repo(tmp_path: Path) -> Path:
    """A temporary directory mimicking a GitHub repo with a plugin."""
    repo = tmp_path / "repo"
    repo.mkdir()

    plugin_dir = repo / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"name": "test-plugin", "description": "A test plugin"}')

    skills_dir = repo / "skills" / "skill-a"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: skill-a\n---\n")

    commands_dir = repo / "commands"
    commands_dir.mkdir()
    (commands_dir / "deploy.md").write_text("# Deploy\nDeploy things.")

    (repo / ".mcp.json").write_text('{"mcpServers": {"test": {"command": "echo"}}}')

    return repo
```

**Step 2: Run all tests**

Run: `cd cli && uv run pytest -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add cli/tests/conftest.py
git commit -m "feat(cli): add shared test fixtures for project dirs and sample repos"
```

---

### Task 19: Update pyproject.toml dependencies + __init__.py

**Files:**
- Modify: `cli/pyproject.toml`
- Modify: `cli/src/openforge/__init__.py`

**Step 1: Update pyproject.toml**

Add missing dependencies: `tomli`, `tomli-w`, `pytest-tmp-files`. Set version string in `__init__.py`.

```toml
[project]
dependencies = [
    "typer>=0.15.0",
    "httpx>=0.28.0",
    "rich>=13.9.0",
    "pyyaml>=6.0.0",
    "tomli>=2.0.0; python_version < '3.11'",
    "tomli-w>=1.0.0",
]

[dependency-groups]
dev = [
    "pyright>=1.1.390",
    "pytest>=8.3.0",
    "pytest-tmp-files>=0.0.2",
]
```

**Step 2: Set version in __init__.py**

```python
from __future__ import annotations

__version__ = "0.1.0"
```

**Step 3: Run full test suite + pyright**

Run: `cd cli && uv sync && uv run pytest -v && uv run pyright src/`
Expected: ALL PASS, 0 pyright errors

**Step 4: Commit**

```bash
git add cli/pyproject.toml cli/src/openforge/__init__.py
git commit -m "chore(cli): update dependencies and set version"
```

---

### Task 20: End-to-end smoke test

**Files:**
- Modify: `cli/tests/test_add.py` (add E2E test)

**Step 1: Write E2E test**

An integration test that exercises the full flow without mocking (except git clone — use a local fixture repo instead):

```python
def test_add_e2e_with_local_repo(tmp_path: Path, sample_skill_repo: Path) -> None:
    """Full flow: add from a local path, verify canonical storage, symlinks, lock file."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Simulate what add does with a pre-fetched repo
    from openforge.plugins import detect_content
    from openforge.installer import create_canonical_storage, install_to_all_agents
    from openforge.lock import add_lock_entry, read_lock
    from openforge.types import LockEntry, SourceType

    content = detect_content(sample_skill_repo)
    assert len(content.skills) == 3

    for skill in content.skills:
        create_canonical_storage(
            source_dir=sample_skill_repo / "skills" / skill.name,
            project_dir=project_dir,
            name=skill.name,
            content_type=content.content_type,
            is_global=False,
        )

    # Verify canonical storage
    for name in ["lint", "format", "test"]:
        assert (project_dir / ".agents" / "skills" / name / "SKILL.md").exists()

    # Verify lock file
    lock_path = project_dir / ".openforge-lock.json"
    for skill in content.skills:
        add_lock_entry(lock_path, skill.name, LockEntry(
            type=content.content_type,
            source="acme/tools",
            source_type=SourceType.GITHUB,
            git_url="https://github.com/acme/tools",
            git_sha="abc123",
            skills=[skill.name],
            agents_installed=[],
            installed_at="2026-03-06T12:00:00Z",
            updated_at="2026-03-06T12:00:00Z",
        ))

    lock = read_lock(lock_path)
    assert len(lock.entries) == 3
```

**Step 2: Run all tests**

Run: `cd cli && uv run pytest -v`
Expected: ALL PASS

**Step 3: Run pyright on everything**

Run: `cd cli && uv run pyright src/`
Expected: 0 errors

**Step 4: Final commit**

```bash
git add cli/tests/test_add.py
git commit -m "test(cli): add end-to-end smoke test for full install flow"
```

---

### Task 21: Update project tracker

**Step 1: Update project tracker**

Update the project tracker (milestone progress, close completed issues) to reflect Phase 1 CLI MVP implementation status.

**Step 2: Commit any remaining changes**

```bash
git status  # verify clean
```

---

## Summary

| Task | Module | What it builds |
|------|--------|---------------|
| 1 | types.py | Shared data models |
| 2 | source_parser.py | Parse owner/repo@skill syntax |
| 3 | config_file.py | TOML config with precedence |
| 4 | lock.py | Lock file JSON read/write |
| 5 | skills.py | SKILL.md frontmatter parsing |
| 6 | plugins.py | plugin.json + content detection |
| 7 | agents/ | 51-agent registry |
| 8 | providers/github.py | Git clone provider |
| 9 | installer.py | Symlink-based installation |
| 10 | adapters/claude.py | Claude Code MCP/commands/hooks |
| 11 | adapters/cursor.py | Cursor MCP/commands |
| 12 | telemetry.py | Fire-and-forget events |
| 13 | add.py + cli.py | `add` command |
| 14 | remove.py | `remove` command |
| 15 | list.py | `list` command |
| 16 | find.py | `find` command |
| 17 | config.py | `config` command |
| 18 | conftest.py | Shared test fixtures |
| 19 | pyproject.toml | Dependencies + version |
| 20 | test_add.py | E2E smoke test |
| 21 | — | Update project tracker |

**Dependency order:** Tasks 1-6 are independent foundations (can be parallelised). Task 7-8 depend on types. Task 9 depends on 7. Tasks 10-11 depend on 9. Task 12 depends on 3. Tasks 13-17 depend on everything before them. Tasks 18-20 are integration/polish. Task 21 is bookkeeping.
