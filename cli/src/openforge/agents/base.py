from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class AgentConfig:
    name: str
    display_name: str
    skills_dir: str
    global_skills_dir: str | None
    detect: Callable[[], bool]
    capabilities: frozenset[str] = frozenset({"skills"})
    show_in_list: bool = True
