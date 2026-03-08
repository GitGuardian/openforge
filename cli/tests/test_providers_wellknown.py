# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openforge.providers.wellknown import WellKnownProvider
from openforge.types import Source, SourceType

MOCK_INDEX = {
    "version": "1.0.0",
    "skills": [
        {
            "name": "my-skill",
            "description": "A test skill",
            "files": ["SKILL.md", "README.md"],
        }
    ],
}

MOCK_SKILL_MD = "---\nname: my-skill\ndescription: A test skill\n---\n# My Skill"


def test_wellknown_matches() -> None:
    p = WellKnownProvider()
    s = Source(source_type=SourceType.WELL_KNOWN, url="https://example.com")
    assert p.matches(s) is True


def test_wellknown_no_match_github() -> None:
    p = WellKnownProvider()
    s = Source(source_type=SourceType.GITHUB, owner="acme", repo="skills")
    assert p.matches(s) is False


def test_wellknown_no_match_local() -> None:
    p = WellKnownProvider()
    s = Source(source_type=SourceType.LOCAL, local_path="/tmp/foo")
    assert p.matches(s) is False


@patch("openforge.providers.wellknown._http_get")
def test_wellknown_fetch(mock_get: MagicMock, tmp_path: Path) -> None:
    def side_effect(url: str) -> str:
        if "index.json" in url:
            return json.dumps(MOCK_INDEX)
        if "SKILL.md" in url:
            return MOCK_SKILL_MD
        return ""

    mock_get.side_effect = side_effect

    p = WellKnownProvider()
    s = Source(source_type=SourceType.WELL_KNOWN, url="https://example.com")
    result = p.fetch(s, tmp_path)
    assert (result.content_root / "my-skill" / "SKILL.md").exists()
    assert result.sha != ""


@patch("openforge.providers.wellknown._http_get")
def test_wellknown_no_index(mock_get: MagicMock, tmp_path: Path) -> None:
    mock_get.side_effect = Exception("404")
    p = WellKnownProvider()
    s = Source(source_type=SourceType.WELL_KNOWN, url="https://example.com")
    with pytest.raises(ValueError, match="could not fetch"):
        p.fetch(s, tmp_path)


@patch("openforge.providers.wellknown._http_get")
def test_wellknown_fetch_content_hash_deterministic(mock_get: MagicMock, tmp_path: Path) -> None:
    """Same content produces same hash."""

    def side_effect(url: str) -> str:
        if "index.json" in url:
            return json.dumps(MOCK_INDEX)
        if "SKILL.md" in url:
            return MOCK_SKILL_MD
        return ""

    mock_get.side_effect = side_effect

    p = WellKnownProvider()
    s = Source(source_type=SourceType.WELL_KNOWN, url="https://example.com")
    r1 = p.fetch(s, tmp_path)

    # Create a fresh dest for second fetch
    tmp_path2 = tmp_path / "second"
    tmp_path2.mkdir()
    mock_get.side_effect = side_effect
    r2 = p.fetch(s, tmp_path2)

    assert r1.sha == r2.sha
