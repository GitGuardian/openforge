from __future__ import annotations

from pathlib import Path
from typing import Protocol

from openforge.types import Source


class Provider(Protocol):
    """Protocol that all source providers must implement."""

    def fetch(self, source: Source, dest: Path) -> str:
        """Fetch content to dest directory. Return git SHA."""
        ...
