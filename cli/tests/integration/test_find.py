# SPDX-License-Identifier: Apache-2.0
"""Integration tests for find --remote / search_forge.

search_forge uses urllib.request.urlopen (not httpx), so we patch
openforge.providers.forge._http_get to avoid real network calls.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from openforge.providers.forge import search_forge


def _marketplace_json(packages: list[dict[str, object]]) -> str:
    """Build a fake marketplace.json response string."""
    return json.dumps({"version": "1", "packages": packages})


class TestSearchForge:
    """Test search_forge() with mocked HTTP transport."""

    def test_returns_matching_results(self) -> None:
        """search_forge filters packages by name match."""
        packages = [
            {"name": "my-plugin", "description": "does things", "skills": []},
            {"name": "other-tool", "description": "unrelated", "skills": []},
        ]
        with patch(
            "openforge.providers.forge._http_get",
            return_value=_marketplace_json(packages),
        ):
            results = search_forge("my-plugin", forge_url="http://fake-forge.local")

        assert len(results) == 1
        assert results[0]["name"] == "my-plugin"

    def test_returns_description_match(self) -> None:
        """search_forge also matches on description field."""
        packages = [
            {"name": "plugin-a", "description": "advanced search helper", "skills": []},
            {"name": "plugin-b", "description": "unrelated", "skills": []},
        ]
        with patch(
            "openforge.providers.forge._http_get",
            return_value=_marketplace_json(packages),
        ):
            results = search_forge("search helper", forge_url="http://fake-forge.local")

        assert any(r["name"] == "plugin-a" for r in results)

    def test_returns_empty_list_on_no_match(self) -> None:
        """search_forge returns [] when no packages match."""
        packages = [{"name": "unrelated", "description": "nothing here", "skills": []}]
        with patch(
            "openforge.providers.forge._http_get",
            return_value=_marketplace_json(packages),
        ):
            results = search_forge("zzz_no_match_zzz", forge_url="http://fake-forge.local")

        assert results == []

    def test_returns_empty_list_for_empty_marketplace(self) -> None:
        """search_forge returns [] when marketplace has no packages."""
        with patch(
            "openforge.providers.forge._http_get",
            return_value=_marketplace_json([]),
        ):
            results = search_forge("anything", forge_url="http://fake-forge.local")

        assert results == []
