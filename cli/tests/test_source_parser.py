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
