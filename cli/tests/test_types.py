# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from openforge.types import (
    ContentType,
    DetectedContent,
    LockFile,
    SkillInfo,
    Source,
    SourceType,
)


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


# --- Phase 4: Multi-provider type extensions ---


def test_source_type_values() -> None:
    """All SourceType enum values exist and serialize correctly."""
    assert SourceType.GITHUB.value == "github"
    assert SourceType.GITLAB.value == "gitlab"
    assert SourceType.GIT.value == "git"
    assert SourceType.LOCAL.value == "local"
    assert SourceType.WELL_KNOWN.value == "well_known"
    assert SourceType.FORGE.value == "forge"


def test_source_git_url_github() -> None:
    """GitHub sources derive git_url from owner/repo."""
    s = Source(owner="acme", repo="skills")
    assert s.git_url == "https://github.com/acme/skills"


def test_source_git_url_explicit() -> None:
    """GitLab/other sources use the explicit url field."""
    s = Source(source_type=SourceType.GITLAB, url="https://gitlab.com/acme/skills")
    assert s.git_url == "https://gitlab.com/acme/skills"


def test_source_local_path() -> None:
    """Local sources store a local_path."""
    s = Source(source_type=SourceType.LOCAL, local_path="/tmp/my-plugin")
    assert s.local_path == "/tmp/my-plugin"


def test_source_shorthand_local() -> None:
    """Local sources use local_path as shorthand."""
    s = Source(source_type=SourceType.LOCAL, local_path="/tmp/my-plugin")
    assert s.shorthand == "/tmp/my-plugin"


def test_source_shorthand_well_known() -> None:
    """Well-known sources use url as shorthand."""
    s = Source(source_type=SourceType.WELL_KNOWN, url="https://mintlify.com/docs")
    assert s.shorthand == "https://mintlify.com/docs"


def test_source_shorthand_forge() -> None:
    """Forge sources use url as shorthand."""
    s = Source(source_type=SourceType.FORGE, url="https://openforge.example.com/my-plugin")
    assert s.shorthand == "https://openforge.example.com/my-plugin"


def test_source_shorthand_gitlab_with_owner_repo() -> None:
    """GitLab sources with owner/repo use owner/repo shorthand."""
    s = Source(
        source_type=SourceType.GITLAB,
        owner="acme",
        repo="skills",
        url="https://gitlab.com/acme/skills",
    )
    assert s.shorthand == "acme/skills"


def test_source_shorthand_git_url_only() -> None:
    """Generic git source with only url falls back to url for shorthand."""
    s = Source(source_type=SourceType.GIT, url="git@example.com:acme/skills.git")
    assert s.shorthand == "git@example.com:acme/skills.git"


def test_source_defaults_backward_compatible() -> None:
    """Existing Source(owner=, repo=) usage still works without source_type."""
    s = Source(owner="acme", repo="tools", skill_name="lint")
    assert s.source_type == SourceType.GITHUB
    assert s.shorthand == "acme/tools@lint"
    assert s.git_url == "https://github.com/acme/tools"
    assert s.url is None
    assert s.local_path is None
