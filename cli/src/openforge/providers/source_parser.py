# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re

from openforge.types import Source, SourceType

_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+?)(?:\.git)?(?:/tree/(?P<ref>[^/]+)(?:/(?P<subdir>.+))?)?/?$"
)

_GITLAB_URL_RE = re.compile(
    r"^https://gitlab\.com/(?P<path>[a-zA-Z0-9_./-]+?)(?:\.git)?(?:/-/tree/(?P<ref>[^/]+)(?:/(?P<subdir>.+))?)?/?$"
)

_GITLAB_PREFIX_RE = re.compile(r"^gitlab:(?P<path>[a-zA-Z0-9_./-]+)$")

_SSH_RE = re.compile(r"^git@[a-zA-Z0-9_.:-]+:[a-zA-Z0-9_./-]+(?:\.git)?$")

_LOCAL_PATH_RE = re.compile(r"^(?:\./|/|\.\./).*$")

_BRANCH_RE = re.compile(r"#(?P<ref>[^#]+)$")

_FORGE_PREFIX_RE = re.compile(r"^forge:(?P<name>.+)$")

_SHORTHAND_RE = re.compile(
    r"^(?P<owner>[a-zA-Z0-9_.-]+)/(?P<repo>[a-zA-Z0-9_.-]+)(?:@(?P<skill>[^/#]+))?(?:/(?P<subdir>.+))?$"
)


def parse_source(raw: str) -> Source:
    """Parse a source string into a Source object.

    Supports:
      - owner/repo
      - owner/repo@skill-name
      - owner/repo#branch
      - owner/repo@skill#branch
      - owner/repo/path/to/subdir
      - https://github.com/owner/repo
      - https://github.com/owner/repo/tree/ref/path
      - https://gitlab.com/group/repo
      - https://gitlab.com/group/subgroup/repo
      - gitlab:owner/repo
      - git@host:owner/repo.git
      - ./local-path, ../local-path, /absolute-path
      - forge:plugin-name
      - https://other-host.com/path  (well-known)
    """
    raw = raw.strip()
    if not raw:
        raise ValueError("Source cannot be empty")

    if raw.startswith("http://"):
        msg = f"HTTPS required: {raw!r}. Plain HTTP URLs are not allowed."
        raise ValueError(msg)

    # 1. forge: prefix
    m = _FORGE_PREFIX_RE.match(raw)
    if m:
        return Source(source_type=SourceType.FORGE, url=m.group("name"))

    # 2. gitlab: prefix
    m = _GITLAB_PREFIX_RE.match(raw)
    if m:
        return Source(
            source_type=SourceType.GITLAB,
            url=f"https://gitlab.com/{m.group('path')}",
        )

    # 3. Local paths
    if _LOCAL_PATH_RE.match(raw):
        return Source(source_type=SourceType.LOCAL, local_path=raw)

    # 4. Extract #branch ref (before other URL/shorthand parsing)
    ref_from_hash: str | None = None
    m = _BRANCH_RE.search(raw)
    if m:
        ref_from_hash = m.group("ref")
        raw = raw[: m.start()]

    # 5. SSH URLs
    if _SSH_RE.match(raw):
        return Source(source_type=SourceType.GIT, url=raw, ref=ref_from_hash)

    # 6. GitLab HTTPS URLs
    m = _GITLAB_URL_RE.match(raw)
    if m:
        return Source(
            source_type=SourceType.GITLAB,
            url=raw,
            ref=m.group("ref") or ref_from_hash,
            subdir=m.group("subdir"),
        )

    # 7. GitHub HTTPS URLs
    m = _GITHUB_URL_RE.match(raw)
    if m:
        return Source(
            owner=m.group("owner"),
            repo=m.group("repo"),
            ref=m.group("ref") or ref_from_hash,
            subdir=m.group("subdir"),
        )

    # 8. Well-known HTTPS URLs (non-GitHub, non-GitLab)
    if raw.startswith("https://"):
        return Source(source_type=SourceType.WELL_KNOWN, url=raw)

    # 9. GitHub shorthand (owner/repo, owner/repo@skill, owner/repo/subdir)
    m = _SHORTHAND_RE.match(raw)
    if m:
        return Source(
            owner=m.group("owner"),
            repo=m.group("repo"),
            skill_name=m.group("skill"),
            subdir=m.group("subdir"),
            ref=ref_from_hash,
        )

    msg = f"Invalid source: {raw!r}"
    raise ValueError(msg)
