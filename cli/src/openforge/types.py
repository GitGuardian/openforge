# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ContentType(Enum):
    PLUGIN = "plugin"
    SKILL = "skill"


class SourceType(Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    GIT = "git"
    LOCAL = "local"
    WELL_KNOWN = "well_known"
    FORGE = "forge"


@dataclass(frozen=True)
class Source:
    """Parsed source reference (e.g. owner/repo@skill-name)."""

    source_type: SourceType = SourceType.GITHUB
    owner: str = ""
    repo: str = ""
    skill_name: str | None = None
    subdir: str | None = None
    ref: str | None = None
    url: str | None = None
    local_path: str | None = None

    @property
    def shorthand(self) -> str:
        if self.source_type == SourceType.LOCAL:
            return self.local_path or ""
        if self.source_type in (SourceType.WELL_KNOWN, SourceType.FORGE):
            return self.url or ""
        base = f"{self.owner}/{self.repo}" if self.owner else (self.url or "")
        if self.skill_name:
            return f"{base}@{self.skill_name}"
        return base

    @property
    def git_url(self) -> str:
        if self.url:
            return self.url
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
