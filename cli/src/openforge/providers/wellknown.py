# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast
from urllib.error import URLError
from urllib.request import Request, urlopen

from openforge.providers.base import FetchResult
from openforge.types import Source, SourceType
from openforge.validation import validate_name, validate_path_containment

_MAX_FILE_SIZE = 1_000_000  # 1MB per file


def _http_get(url: str) -> str:
    """Fetch a URL and return the response body as a string."""
    req = Request(url, headers={"User-Agent": "openforge-cli"})  # noqa: S310
    with urlopen(req, timeout=30) as resp:  # noqa: S310  # nosec B310
        return resp.read(_MAX_FILE_SIZE).decode()


class WellKnownProvider:
    """Fetch skills from a .well-known/skills/ endpoint."""

    def matches(self, source: Source) -> bool:
        """Return True if this provider handles the given source type."""
        return source.source_type == SourceType.WELL_KNOWN

    def fetch(self, source: Source, dest: Path) -> FetchResult:
        """Fetch skills from a .well-known/skills/index.json endpoint."""
        base_url = (source.url or "").rstrip("/")

        # Try /.well-known/skills/index.json
        index_url = f"{base_url}/.well-known/skills/index.json"
        try:
            raw = _http_get(index_url)
        except (URLError, OSError, json.JSONDecodeError) as exc:
            msg = f"could not fetch well-known index from {index_url}: {exc}"
            raise ValueError(msg) from exc

        index = cast(dict[str, Any], json.loads(raw))
        skills_data = cast(list[dict[str, Any]], index.get("skills", []))
        if not skills_data:
            msg = f"no skills found in index at {index_url}"
            raise ValueError(msg)

        hasher = hashlib.sha256()
        dest.mkdir(parents=True, exist_ok=True)

        for skill in skills_data:
            name = str(skill.get("name", ""))
            validate_name(name)
            files = cast(list[str], skill.get("files", ["SKILL.md"]))
            skill_dir = dest / name
            skill_dir.mkdir(parents=True, exist_ok=True)

            for fname in files:
                file_dest = (skill_dir / fname).resolve()
                validate_path_containment(file_dest, skill_dir)

                file_url = f"{base_url}/.well-known/skills/{name}/{fname}"
                try:
                    content = _http_get(file_url)
                except (URLError, OSError):
                    if fname == "SKILL.md":
                        raise  # SKILL.md is required
                    continue
                file_dest.write_text(content)
                hasher.update(content.encode())

        return FetchResult(sha=hasher.hexdigest()[:12], content_root=dest)
