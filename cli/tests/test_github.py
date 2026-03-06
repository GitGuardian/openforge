# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

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


def test_fetch_token_not_in_clone_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When GITHUB_TOKEN is set, the token must NOT appear in the clone URL."""
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_secret123")

    mock_run = MagicMock()
    # First call: git clone; second call: git rev-parse
    mock_run.return_value.stdout = "abc123\n"

    provider = GitHubProvider()
    source = Source(owner="acme", repo="tools")
    dest = tmp_path / "repo"

    with patch("openforge.providers.github.subprocess.run", mock_run):
        provider.fetch(source, dest)

    clone_call_args: list[str] = mock_run.call_args_list[0][0][0]
    # The token must not be embedded in any argument (especially the URL)
    for arg in clone_call_args:
        assert "ghp_secret123" not in arg or arg.startswith("http.extraheader=")
    # The URL argument itself must be a plain https://github.com URL
    url_args = [a for a in clone_call_args if a.startswith("https://")]
    assert len(url_args) == 1
    assert "ghp_secret123" not in url_args[0]
    # The extraheader config must be present
    assert "http.extraheader=Authorization: Bearer ghp_secret123" in clone_call_args
