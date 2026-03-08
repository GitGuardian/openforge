# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
from pathlib import Path

from openforge.providers.base import FetchResult
from openforge.types import Source, SourceType


class LocalProvider:
    """Fetch content from a local filesystem path."""

    def matches(self, source: Source) -> bool:
        """Return True if this provider handles the given source type."""
        return source.source_type == SourceType.LOCAL

    def fetch(self, source: Source, dest: Path) -> FetchResult:  # noqa: ARG002
        """Return a FetchResult pointing to the local path with a content hash."""
        local_path = Path(source.local_path or "").resolve()
        if not local_path.exists():
            msg = f"Local path does not exist: {local_path}"
            raise FileNotFoundError(msg)

        # Content hash based on file paths + mtimes
        hasher = hashlib.sha256()
        for f in sorted(local_path.rglob("*")):
            if f.is_file():
                hasher.update(str(f.relative_to(local_path)).encode())
                hasher.update(str(f.stat().st_mtime_ns).encode())

        return FetchResult(sha=hasher.hexdigest()[:12], content_root=local_path)
