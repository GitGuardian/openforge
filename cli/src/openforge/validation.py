# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re
from pathlib import Path

_SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def validate_name(name: str, kind: str = "name") -> str:
    """Validate and return a safe name. Raises ValueError if invalid."""
    if not _SAFE_NAME_RE.match(name):
        msg = f"Invalid {kind}: {name!r}. Must match [a-zA-Z0-9_-] and be 1-64 chars."
        raise ValueError(msg)
    return name


def validate_path_containment(child: Path, parent: Path) -> None:
    """Ensure resolved child is within resolved parent. Raises ValueError if not."""
    resolved_child = child.resolve()
    resolved_parent = parent.resolve()
    if not resolved_child.is_relative_to(resolved_parent):
        msg = f"Path escape detected: {child} resolves outside {parent}"
        raise ValueError(msg)
