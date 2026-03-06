from __future__ import annotations

import re

from openforge.types import Source


_GITHUB_URL_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?(?:/tree/(?P<ref>[^/]+)(?:/(?P<subdir>.+))?)?/?$"
)

_SHORTHAND_RE = re.compile(
    r"^(?P<owner>[^/@]+)/(?P<repo>[^/@]+)(?:@(?P<skill>[^/]+))?(?:/(?P<subdir>.+))?$"
)


def parse_source(raw: str) -> Source:
    """Parse a source string into a Source object.

    Supports:
      - owner/repo
      - owner/repo@skill-name
      - owner/repo/path/to/subdir
      - https://github.com/owner/repo
      - https://github.com/owner/repo/tree/ref/path
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("Source cannot be empty")

    # Try GitHub URL first
    if raw.startswith(("http://", "https://")):
        m = _GITHUB_URL_RE.match(raw)
        if not m:
            raise ValueError(f"Invalid source URL: {raw}")
        return Source(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref"),
            subdir=m.group("subdir"),
        )

    # Try shorthand
    m = _SHORTHAND_RE.match(raw)
    if not m:
        raise ValueError(f"Invalid source: {raw}")

    return Source(
        owner=m.group("owner"),
        repo=m.group("repo"),
        skill_name=m.group("skill"),
        subdir=m.group("subdir"),
    )
