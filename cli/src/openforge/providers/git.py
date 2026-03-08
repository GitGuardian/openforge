# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
import subprocess  # nosec B404
from pathlib import Path

from openforge.providers.base import FetchResult
from openforge.types import Source, SourceType
from openforge.validation import validate_path_containment

_GIT_SOURCE_TYPES = frozenset({SourceType.GITHUB, SourceType.GITLAB, SourceType.GIT})


class GitProvider:
    """Fetch content from git repos (GitHub, GitLab, generic git URLs)."""

    def matches(self, source: Source) -> bool:
        """Return True if this provider handles the given source type."""
        return source.source_type in _GIT_SOURCE_TYPES

    def fetch(self, source: Source, dest: Path) -> FetchResult:
        """Clone a git repo to dest. Return FetchResult with SHA and content root."""
        url = source.git_url
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

        cmd: list[str] = ["git"]
        env = dict(os.environ)

        # Only inject token for HTTPS URLs
        if token and url.startswith("https://"):
            cmd.extend(["-c", f"http.extraheader=Authorization: Bearer {token}"])
            env["GIT_TERMINAL_PROMPT"] = "0"

        cmd.extend(["clone", "--depth", "1"])

        if source.ref:
            cmd.extend(["--branch", source.ref])

        cmd.extend([url, str(dest)])
        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)  # nosec B603

        result = subprocess.run(  # nosec B603 B607
            ["git", "-C", str(dest), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        sha = result.stdout.strip()

        content_root = dest
        if source.subdir:
            content_root = dest / source.subdir
            validate_path_containment(content_root, dest)

        return FetchResult(sha=sha, content_root=content_root)
