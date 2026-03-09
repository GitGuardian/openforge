# SPDX-License-Identifier: Apache-2.0
"""Integration tests for search_forge and ForgeProvider — HTTP transport layer.

search_forge uses urllib.request (not httpx), so we mock _http_get to test
the full marketplace fetch → parse → filter chain without hitting the network.
These tests exercise code paths not covered by the unit tests:
- Full JSON parsing of marketplace responses
- Search filtering by name, description, and tags
- ForgeProvider git URL resolution from marketplace data
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from openforge.providers.forge import ForgeProvider, search_forge
from openforge.types import Source, SourceType


class TestSearchForgeTransport:
    """Test search_forge() with realistic marketplace data."""

    def _marketplace_json(self, packages: list[dict[str, object]]) -> str:
        """Build a marketplace.json string from a package list."""
        return json.dumps({"packages": packages})

    def test_search_matches_by_name(self) -> None:
        """search_forge matches plugins by name (case-insensitive)."""
        data = self._marketplace_json(
            [
                {"name": "security-scanner", "description": "Scan vulnerabilities", "tags": []},
                {"name": "code-formatter", "description": "Format code", "tags": []},
            ]
        )

        with patch("openforge.providers.forge._http_get", return_value=data):
            results = search_forge("security", forge_url="https://forge.test")
            assert len(results) == 1
            assert results[0]["name"] == "security-scanner"

    def test_search_matches_by_description(self) -> None:
        """search_forge matches plugins by description."""
        data = self._marketplace_json(
            [
                {"name": "plugin-a", "description": "Lint your Python code", "tags": []},
                {"name": "plugin-b", "description": "Format YAML files", "tags": []},
            ]
        )

        with patch("openforge.providers.forge._http_get", return_value=data):
            results = search_forge("python", forge_url="https://forge.test")
            assert len(results) == 1
            assert results[0]["name"] == "plugin-a"

    def test_search_matches_by_tag(self) -> None:
        """search_forge matches plugins by tags."""
        data = self._marketplace_json(
            [
                {"name": "plugin-a", "description": "Does stuff", "tags": ["quality", "lint"]},
                {"name": "plugin-b", "description": "Other stuff", "tags": ["deploy"]},
            ]
        )

        with patch("openforge.providers.forge._http_get", return_value=data):
            results = search_forge("lint", forge_url="https://forge.test")
            assert len(results) == 1
            assert results[0]["name"] == "plugin-a"

    def test_search_case_insensitive(self) -> None:
        """search_forge is case-insensitive."""
        data = self._marketplace_json(
            [{"name": "Security-Scanner", "description": "Scan", "tags": []}]
        )

        with patch("openforge.providers.forge._http_get", return_value=data):
            results = search_forge("SECURITY", forge_url="https://forge.test")
            assert len(results) == 1

    def test_search_no_matches_returns_empty(self) -> None:
        """search_forge returns empty list when nothing matches."""
        data = self._marketplace_json(
            [{"name": "plugin-a", "description": "Does stuff", "tags": []}]
        )

        with patch("openforge.providers.forge._http_get", return_value=data):
            results = search_forge("nonexistent", forge_url="https://forge.test")
            assert results == []

    def test_search_fetches_correct_url(self) -> None:
        """search_forge fetches marketplace.json from the correct Forge URL."""
        data = self._marketplace_json([])

        with patch("openforge.providers.forge._http_get", return_value=data) as mock_get:
            search_forge("test", forge_url="https://my-forge.example.com")
            mock_get.assert_called_once_with("https://my-forge.example.com/api/marketplace.json")


class TestForgeProviderTransport:
    """Test ForgeProvider.fetch() marketplace lookup logic."""

    def test_provider_matches_forge_source(self) -> None:
        """ForgeProvider matches FORGE source type."""
        provider = ForgeProvider()
        source = Source(source_type=SourceType.FORGE, url="my-plugin")
        assert provider.matches(source)

    def test_provider_rejects_github_source(self) -> None:
        """ForgeProvider does not match GITHUB source type."""
        provider = ForgeProvider()
        source = Source(source_type=SourceType.GITHUB, url="owner/repo")
        assert not provider.matches(source)

    def test_provider_raises_on_unknown_plugin(self) -> None:
        """ForgeProvider raises ValueError when plugin not in marketplace."""
        data = json.dumps({"packages": [{"name": "other-plugin"}]})
        provider = ForgeProvider()
        source = Source(source_type=SourceType.FORGE, url="nonexistent")

        with (
            patch("openforge.providers.forge._http_get", return_value=data),
            pytest.raises(ValueError, match="not found"),
        ):
            provider.fetch(source, dest=None, forge_url="https://forge.test")  # type: ignore[arg-type]
