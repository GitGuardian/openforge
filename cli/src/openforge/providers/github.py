from __future__ import annotations

import os
import subprocess
from pathlib import Path

from openforge.types import Source
from openforge.validation import validate_path_containment


class GitHubProvider:
    """Fetch content from GitHub repos via git clone."""

    def fetch(self, source: Source, dest: Path) -> str:
        """Clone a GitHub repo to dest. Return the HEAD SHA."""
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

        url = source.git_url
        cmd: list[str] = ["git"]
        env = dict(os.environ)
        if token:
            cmd.extend(["-c", f"http.extraheader=Authorization: Bearer {token}"])
            env["GIT_TERMINAL_PROMPT"] = "0"
        cmd.extend(["clone", "--depth", "1"])
        if source.ref:
            cmd.extend(["--branch", source.ref])
        cmd.extend([url, str(dest)])

        subprocess.run(cmd, check=True, capture_output=True, text=True, env=env)

        result = subprocess.run(
            ["git", "-C", str(dest), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def content_root(self, source: Source, dest: Path) -> Path:
        """Return the content root within the cloned repo."""
        if source.subdir:
            result = dest / source.subdir
            validate_path_containment(result, dest)
            return result
        return dest
