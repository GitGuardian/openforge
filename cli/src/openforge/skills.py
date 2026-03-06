from __future__ import annotations

from pathlib import Path
from typing import cast

from openforge.types import SkillInfo
from openforge.validation import validate_name, validate_path_containment

_RGLOB_EXCLUDED_DIRS = frozenset({".git", "node_modules", "__pycache__", "vendor"})


def parse_skill_md(path: Path) -> SkillInfo:
    """Parse a single SKILL.md file, extracting YAML frontmatter.

    If no frontmatter is present, infer the name from the parent directory.
    """
    text = path.read_text(encoding="utf-8")
    name = ""
    description = ""
    tags: tuple[str, ...] = ()

    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            import yaml

            frontmatter_raw = text[4:end]
            data: dict[str, object] = yaml.safe_load(frontmatter_raw) or {}
            name = str(data.get("name", ""))
            description = str(data.get("description", ""))
            raw_tags: object = data.get("tags")
            if isinstance(raw_tags, list):
                tags = tuple(str(item) for item in cast(list[object], raw_tags))

    if not name:
        name = path.parent.name

    validate_name(name, kind="skill name")

    return SkillInfo(
        name=name,
        description=description,
        tags=tags,
        path=str(path.parent),
    )


def find_skills_in_dir(root: Path) -> list[SkillInfo]:
    """Scan a directory for skills using a priority-based search.

    Priority order:
    1. Root SKILL.md (single skill)
    2. skills/ directory (each subdir with SKILL.md)
    3. skills/.curated/, skills/.experimental/, skills/.system/ subdirs
    4. Agent-specific dirs: .claude/skills/, .agents/skills/
    5. Recursive search as fallback
    """
    # 1. Root SKILL.md
    root_skill = root / "SKILL.md"
    if root_skill.is_file():
        return [parse_skill_md(root_skill)]

    results: list[SkillInfo] = []

    # 2. skills/ directory — direct subdirs
    skills_dir = root / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            if child.is_dir() and not child.name.startswith("."):
                skill_md = child / "SKILL.md"
                if skill_md.is_file():
                    results.append(parse_skill_md(skill_md))

        # 3. Curated / experimental / system subdirs
        for special in (".curated", ".experimental", ".system"):
            special_dir = skills_dir / special
            if special_dir.is_dir():
                for child in sorted(special_dir.iterdir()):
                    if child.is_dir():
                        skill_md = child / "SKILL.md"
                        if skill_md.is_file():
                            results.append(parse_skill_md(skill_md))

    if results:
        return results

    # 4. Agent-specific dirs
    for agent_base in (".claude/skills", ".agents/skills"):
        agent_dir = root / agent_base
        if agent_dir.is_dir():
            for child in sorted(agent_dir.iterdir()):
                if child.is_dir():
                    skill_md = child / "SKILL.md"
                    if skill_md.is_file():
                        results.append(parse_skill_md(skill_md))

    if results:
        return results

    # 5. Recursive fallback
    for skill_md in sorted(root.rglob("SKILL.md")):
        # Limit search depth (SKILL.md at depth 4 means 3 dirs deep)
        rel = skill_md.relative_to(root)
        if len(rel.parts) > 4:
            continue
        # Skip excluded directories
        if _RGLOB_EXCLUDED_DIRS.intersection(skill_md.parts):
            continue
        # Validate path is within root
        try:
            validate_path_containment(skill_md, root)
        except ValueError:
            continue
        results.append(parse_skill_md(skill_md))

    return results
