# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openforge.providers.forge import ForgeProvider, search_forge
from openforge.types import Source, SourceType

MOCK_MARKETPLACE = {
    "version": "0.1.0",
    "packages": [
        {
            "name": "security-scanner",
            "description": "Scan for vulnerabilities",
            "source": {"type": "url", "url": "https://github.com/acme/security"},
        },
        {
            "name": "code-review",
            "description": "AI code review",
            "source": {"type": "url", "url": "https://github.com/acme/review"},
        },
    ],
}


def test_forge_provider_matches() -> None:
    p = ForgeProvider()
    s = Source(source_type=SourceType.FORGE, url="my-plugin")
    assert p.matches(s) is True


def test_forge_provider_no_match_github() -> None:
    p = ForgeProvider()
    s = Source(source_type=SourceType.GITHUB, owner="acme", repo="skills")
    assert p.matches(s) is False


def test_forge_provider_no_match_local() -> None:
    p = ForgeProvider()
    s = Source(source_type=SourceType.LOCAL, local_path="/tmp/foo")
    assert p.matches(s) is False


@patch("openforge.providers.forge._http_get")
def test_search_forge(mock_get: MagicMock) -> None:
    mock_get.return_value = json.dumps(MOCK_MARKETPLACE)
    results = search_forge("security", forge_url="https://forge.example.com")
    assert len(results) == 1
    assert results[0]["name"] == "security-scanner"


@patch("openforge.providers.forge._http_get")
def test_search_forge_by_description(mock_get: MagicMock) -> None:
    mock_get.return_value = json.dumps(MOCK_MARKETPLACE)
    results = search_forge("code review", forge_url="https://forge.example.com")
    assert len(results) == 1
    assert results[0]["name"] == "code-review"


@patch("openforge.providers.forge._http_get")
def test_search_forge_no_results(mock_get: MagicMock) -> None:
    mock_get.return_value = json.dumps(MOCK_MARKETPLACE)
    results = search_forge("nonexistent", forge_url="https://forge.example.com")
    assert len(results) == 0


@patch("openforge.providers.forge._http_get")
def test_search_forge_case_insensitive(mock_get: MagicMock) -> None:
    mock_get.return_value = json.dumps(MOCK_MARKETPLACE)
    results = search_forge("SECURITY", forge_url="https://forge.example.com")
    assert len(results) == 1


@patch("openforge.providers.forge.GitProvider")
@patch("openforge.providers.forge._http_get")
def test_forge_provider_fetch_delegates_to_git(
    mock_get: MagicMock, mock_git_cls: MagicMock
) -> None:
    """ForgeProvider.fetch looks up plugin in marketplace, then delegates to GitProvider."""
    mock_get.return_value = json.dumps(MOCK_MARKETPLACE)

    from openforge.providers.base import FetchResult

    mock_git_instance = MagicMock()
    mock_git_instance.fetch.return_value = FetchResult(sha="abc123", content_root=Path("/tmp/dest"))
    mock_git_cls.return_value = mock_git_instance

    p = ForgeProvider()
    s = Source(source_type=SourceType.FORGE, url="security-scanner")
    result = p.fetch(s, Path("/tmp/dest"), forge_url="https://forge.example.com")

    assert result.sha == "abc123"
    mock_git_instance.fetch.assert_called_once()
    # Verify the git source was constructed with the URL from marketplace
    git_source = mock_git_instance.fetch.call_args[0][0]
    assert git_source.url == "https://github.com/acme/security"


@patch("openforge.providers.forge._http_get")
def test_forge_provider_fetch_not_found(mock_get: MagicMock) -> None:
    mock_get.return_value = json.dumps(MOCK_MARKETPLACE)
    p = ForgeProvider()
    s = Source(source_type=SourceType.FORGE, url="nonexistent-plugin")
    with pytest.raises(ValueError, match="not found"):
        p.fetch(s, Path("/tmp/dest"), forge_url="https://forge.example.com")
