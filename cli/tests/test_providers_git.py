# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from openforge.providers.base import FetchResult, Provider
from openforge.providers.git import GitProvider
from openforge.types import Source, SourceType


def test_git_provider_matches_github() -> None:
    p = GitProvider()
    s = Source(source_type=SourceType.GITHUB, owner="acme", repo="skills")
    assert p.matches(s) is True


def test_git_provider_matches_gitlab() -> None:
    p = GitProvider()
    s = Source(source_type=SourceType.GITLAB, url="https://gitlab.com/acme/skills")
    assert p.matches(s) is True


def test_git_provider_matches_git() -> None:
    p = GitProvider()
    s = Source(source_type=SourceType.GIT, url="git@github.com:acme/skills.git")
    assert p.matches(s) is True


def test_git_provider_no_match_local() -> None:
    p = GitProvider()
    s = Source(source_type=SourceType.LOCAL, local_path="/tmp/foo")
    assert p.matches(s) is False


def test_git_provider_no_match_well_known() -> None:
    p = GitProvider()
    s = Source(source_type=SourceType.WELL_KNOWN, url="https://example.com/skills")
    assert p.matches(s) is False


def test_git_provider_no_match_forge() -> None:
    p = GitProvider()
    s = Source(source_type=SourceType.FORGE, url="https://forge.example.com/plugin")
    assert p.matches(s) is False


def test_git_provider_implements_protocol() -> None:
    """GitProvider satisfies the Provider protocol."""
    p: Provider = GitProvider()
    assert hasattr(p, "matches")
    assert hasattr(p, "fetch")


@patch("openforge.providers.git.subprocess.run")
def test_git_provider_fetch_basic(mock_run: MagicMock) -> None:
    """fetch clones repo and returns FetchResult with SHA."""
    mock_run.side_effect = [
        MagicMock(returncode=0),  # git clone
        MagicMock(returncode=0, stdout="abc123\n"),  # git rev-parse HEAD
    ]
    p = GitProvider()
    s = Source(source_type=SourceType.GITHUB, owner="acme", repo="skills")
    result = p.fetch(s, Path("/tmp/dest"))

    assert isinstance(result, FetchResult)
    assert result.sha == "abc123"
    assert result.content_root == Path("/tmp/dest")


@patch("openforge.providers.git.subprocess.run")
def test_git_provider_fetch_with_subdir(mock_run: MagicMock, tmp_path: Path) -> None:
    """fetch with subdir returns content_root pointing to subdir."""
    subdir = tmp_path / "skills"
    subdir.mkdir()

    mock_run.side_effect = [
        MagicMock(returncode=0),  # git clone
        MagicMock(returncode=0, stdout="def456\n"),  # git rev-parse HEAD
    ]
    p = GitProvider()
    s = Source(source_type=SourceType.GITHUB, owner="acme", repo="skills", subdir="skills")
    result = p.fetch(s, tmp_path)

    assert result.sha == "def456"
    assert result.content_root == tmp_path / "skills"


@patch("openforge.providers.git.subprocess.run")
def test_git_provider_fetch_with_ref(mock_run: MagicMock) -> None:
    """fetch with ref passes --branch to git clone."""
    mock_run.side_effect = [
        MagicMock(returncode=0),  # git clone
        MagicMock(returncode=0, stdout="ref123\n"),  # git rev-parse HEAD
    ]
    p = GitProvider()
    s = Source(source_type=SourceType.GITHUB, owner="acme", repo="skills", ref="v2")
    result = p.fetch(s, Path("/tmp/dest"))

    assert result.sha == "ref123"
    # Verify --branch was passed
    clone_call = mock_run.call_args_list[0]
    cmd = clone_call[0][0]
    assert "--branch" in cmd
    assert "v2" in cmd


@patch("openforge.providers.git.subprocess.run")
def test_git_provider_fetch_gitlab_url(mock_run: MagicMock) -> None:
    """fetch works with GitLab URLs."""
    mock_run.side_effect = [
        MagicMock(returncode=0),
        MagicMock(returncode=0, stdout="gl789\n"),
    ]
    p = GitProvider()
    s = Source(source_type=SourceType.GITLAB, url="https://gitlab.com/acme/skills")
    result = p.fetch(s, Path("/tmp/dest"))

    assert result.sha == "gl789"
    clone_call = mock_run.call_args_list[0]
    cmd = clone_call[0][0]
    assert "https://gitlab.com/acme/skills" in cmd
