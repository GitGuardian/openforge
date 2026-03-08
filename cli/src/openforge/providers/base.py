# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from openforge.types import Source


@dataclass(frozen=True)
class FetchResult:
    """Result of fetching content from a provider."""

    sha: str  # Git SHA or content hash
    content_root: Path  # Path to the fetched content


class Provider(Protocol):
    """Protocol for content providers."""

    def matches(self, source: Source) -> bool: ...
    def fetch(self, source: Source, dest: Path) -> FetchResult: ...
