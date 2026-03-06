from __future__ import annotations

from pathlib import Path

import pytest

from openforge.providers.github import GitHubProvider
from openforge.types import Source


def test_content_root_subdir_traversal_rejected(tmp_path: Path) -> None:
    """content_root must reject subdir values that escape dest."""
    provider = GitHubProvider()
    source = Source(owner="acme", repo="tools", subdir="../../etc")
    dest = tmp_path / "repo"
    dest.mkdir()
    with pytest.raises(ValueError, match="Path escape detected"):
        provider.content_root(source, dest)


def test_content_root_valid_subdir(tmp_path: Path) -> None:
    """content_root should work for valid subdirs."""
    provider = GitHubProvider()
    source = Source(owner="acme", repo="tools", subdir="skills/lint")
    dest = tmp_path / "repo"
    (dest / "skills" / "lint").mkdir(parents=True)
    result = provider.content_root(source, dest)
    assert result == dest / "skills" / "lint"


def test_content_root_no_subdir(tmp_path: Path) -> None:
    """content_root with no subdir returns dest itself."""
    provider = GitHubProvider()
    source = Source(owner="acme", repo="tools")
    dest = tmp_path / "repo"
    dest.mkdir()
    result = provider.content_root(source, dest)
    assert result == dest
