# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


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
    ref: str | None = None

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
    path: str = ""


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
    plugins: tuple[PluginInfo, ...] = ()
    skills: tuple[SkillInfo, ...] = ()


@dataclass(frozen=True)
class LockEntry:
    """One entry in the lock file."""

    type: ContentType
    source: str
    source_type: SourceType
    git_url: str
    git_sha: str
    skills: tuple[str, ...]
    agents_installed: tuple[str, ...]
    installed_at: str
    updated_at: str


@dataclass
class LockFile:
    """The full .openforge-lock.json contents."""

    version: int = 1
    entries: dict[str, LockEntry] = field(default_factory=lambda: {})
