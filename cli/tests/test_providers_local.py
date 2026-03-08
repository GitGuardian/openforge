# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from openforge.providers.local import LocalProvider
from openforge.types import Source, SourceType


def test_local_provider_matches() -> None:
    p = LocalProvider()
    s = Source(source_type=SourceType.LOCAL, local_path="/tmp/foo")
    assert p.matches(s) is True


def test_local_provider_no_match_github() -> None:
    p = LocalProvider()
    s = Source(source_type=SourceType.GITHUB, owner="acme", repo="skills")
    assert p.matches(s) is False


def test_local_provider_no_match_gitlab() -> None:
    p = LocalProvider()
    s = Source(source_type=SourceType.GITLAB, url="https://gitlab.com/acme/skills")
    assert p.matches(s) is False


def test_local_provider_fetch(tmp_path: Path) -> None:
    skill_dir = tmp_path / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n# My Skill")

    p = LocalProvider()
    s = Source(source_type=SourceType.LOCAL, local_path=str(tmp_path))
    result = p.fetch(s, Path("/unused"))
    assert result.content_root == tmp_path
    assert result.sha != ""


def test_local_provider_fetch_nonexistent() -> None:
    p = LocalProvider()
    s = Source(source_type=SourceType.LOCAL, local_path="/nonexistent/path")
    with pytest.raises(FileNotFoundError):
        p.fetch(s, Path("/unused"))


def test_local_provider_fetch_deterministic(tmp_path: Path) -> None:
    """Same content produces same hash."""
    (tmp_path / "file.txt").write_text("hello")
    p = LocalProvider()
    s = Source(source_type=SourceType.LOCAL, local_path=str(tmp_path))
    r1 = p.fetch(s, Path("/unused"))
    r2 = p.fetch(s, Path("/unused"))
    assert r1.sha == r2.sha
