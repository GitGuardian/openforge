# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast
from urllib.request import Request, urlopen

from openforge.providers.base import FetchResult
from openforge.providers.git import GitProvider
from openforge.types import Source, SourceType

_MAX_RESPONSE_SIZE = 5_000_000  # 5MB


def _http_get(url: str) -> str:
    """Fetch a URL and return the response body as a string."""
    req = Request(url, headers={"User-Agent": "openforge-cli"})  # noqa: S310
    with urlopen(req, timeout=30) as resp:  # noqa: S310  # nosec B310
        return resp.read(_MAX_RESPONSE_SIZE).decode()


def _get_forge_url(forge_url: str | None = None) -> str:
    """Return the Forge URL from the argument, config, or default."""
    if forge_url:
        return forge_url
    from openforge.config_file import load_config

    return load_config().forge_url


def _fetch_marketplace(forge_url: str | None = None) -> list[dict[str, Any]]:
    """Fetch and return the packages list from the Forge marketplace."""
    url = _get_forge_url(forge_url)
    raw = _http_get(f"{url}/api/marketplace.json")
    marketplace = cast(dict[str, Any], json.loads(raw))
    return cast(list[dict[str, Any]], marketplace.get("packages", []))


def search_forge(query: str, *, forge_url: str | None = None) -> list[dict[str, Any]]:
    """Search the Forge marketplace for plugins matching query."""
    packages = _fetch_marketplace(forge_url)
    query_lower = query.lower()
    return [
        p
        for p in packages
        if query_lower in cast(str, p.get("name", "")).lower()
        or query_lower in cast(str, p.get("description", "")).lower()
        or any(query_lower in str(t).lower() for t in cast(list[str], p.get("tags", [])))
    ]


class ForgeProvider:
    """Look up plugins in the Forge marketplace, then delegate to GitProvider."""

    def matches(self, source: Source) -> bool:
        """Return True if this provider handles the given source type."""
        return source.source_type == SourceType.FORGE

    def fetch(self, source: Source, dest: Path, *, forge_url: str | None = None) -> FetchResult:
        """Look up plugin in Forge, then delegate to GitProvider for clone."""
        packages = _fetch_marketplace(forge_url)

        plugin_name = source.url  # forge:plugin-name → url = "plugin-name"
        match = next((p for p in packages if p.get("name") == plugin_name), None)
        if not match:
            msg = f"Plugin '{plugin_name}' not found in Forge"
            raise ValueError(msg)

        # Extract git URL from source field and delegate to GitProvider
        pkg_source = cast(dict[str, str], match.get("source", {}))
        git_url = pkg_source.get("url", "")
        if not git_url:
            msg = f"Plugin '{plugin_name}' has no source URL"
            raise ValueError(msg)

        git_source = Source(source_type=SourceType.GITHUB, url=git_url)
        return GitProvider().fetch(git_source, dest)
