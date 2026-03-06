# SPDX-License-Identifier: Apache-2.0
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
