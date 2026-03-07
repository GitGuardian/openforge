# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    name: str
    display_name: str
    skills_dir: str
    global_skills_dir: str | None
    detect: Callable[[], bool]
    capabilities: frozenset[str] = frozenset({"skills"})
    show_in_list: bool = True
