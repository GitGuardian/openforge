# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from openforge.skills import find_skills_in_dir, parse_skill_md


def test_parse_skill_md_with_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "lint"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: lint\ndescription: Lint your code\ntags:\n  - quality\n  - python\n---\n\n# Lint Skill\n\nLints things.\n"
    )
    skill = parse_skill_md(skill_dir / "SKILL.md")
    assert skill.name == "lint"
    assert skill.description == "Lint your code"
    assert skill.tags == ("quality", "python")


def test_parse_skill_md_no_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "simple"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Simple Skill\n\nDoes stuff.\n")
    skill = parse_skill_md(skill_dir / "SKILL.md")
    assert skill.name == "simple"
    assert skill.description == ""


def test_find_skills_root_skill_md(tmp_path: Path) -> None:
    (tmp_path / "SKILL.md").write_text("---\nname: root-skill\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 1
    assert skills[0].name == "root-skill"


def test_find_skills_skills_directory(tmp_path: Path) -> None:
    skills_dir = tmp_path / "skills"
    for name in ["lint", "format"]:
        d = skills_dir / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 2
    names = {s.name for s in skills}
    assert names == {"lint", "format"}


def test_find_skills_curated_dir(tmp_path: Path) -> None:
    curated = tmp_path / "skills" / ".curated"
    curated.mkdir(parents=True)
    skill_dir = curated / "good-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: good-skill\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 1


def test_find_skills_agent_specific_dir(tmp_path: Path) -> None:
    agent_dir = tmp_path / ".claude" / "skills" / "my-skill"
    agent_dir.mkdir(parents=True)
    (agent_dir / "SKILL.md").write_text("---\nname: my-skill\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 1


def test_skill_path_is_directory_not_file(tmp_path: Path) -> None:
    """skill.path must point to the directory containing SKILL.md, not the file itself."""
    skills_dir = tmp_path / "skills" / "lint"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: lint\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 1
    skill_path = Path(skills[0].path)
    assert skill_path.is_dir(), f"Expected directory, got file: {skill_path}"
    assert skill_path.name == "lint"


def test_parse_skill_md_path_is_directory(tmp_path: Path) -> None:
    """parse_skill_md should set path to the parent directory of SKILL.md."""
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("---\nname: my-skill\n---\n")
    skill = parse_skill_md(skill_md)
    assert Path(skill.path) == skill_dir


def test_parse_skill_md_invalid_name_rejected(tmp_path: Path) -> None:
    """Skill names with path traversal chars must be rejected."""
    skill_dir = tmp_path / "evil"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: ../etc/passwd\n---\n")
    with pytest.raises(ValueError, match="Invalid skill name"):
        parse_skill_md(skill_dir / "SKILL.md")


def test_parse_skill_md_name_with_spaces_rejected(tmp_path: Path) -> None:
    skill_dir = tmp_path / "evil"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: my bad skill\n---\n")
    with pytest.raises(ValueError, match="Invalid skill name"):
        parse_skill_md(skill_dir / "SKILL.md")


def test_parse_skill_md_no_trailing_newline(tmp_path: Path) -> None:
    """Frontmatter ending with --- and no trailing newline must still be parsed."""
    skill_dir = tmp_path / "compact"
    skill_dir.mkdir()
    # Note: no trailing newline after closing ---
    (skill_dir / "SKILL.md").write_text("---\nname: compact\ndescription: No trailing newline\n---")
    skill = parse_skill_md(skill_dir / "SKILL.md")
    assert skill.name == "compact"
    assert skill.description == "No trailing newline"


def test_find_skills_rglob_skips_git_dir(tmp_path: Path) -> None:
    """rglob fallback must skip .git directories."""
    git_dir = tmp_path / ".git" / "hooks"
    git_dir.mkdir(parents=True)
    (git_dir / "SKILL.md").write_text("---\nname: evil\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 0


def test_find_skills_rglob_skips_node_modules(tmp_path: Path) -> None:
    """rglob fallback must skip node_modules."""
    nm_dir = tmp_path / "node_modules" / "pkg"
    nm_dir.mkdir(parents=True)
    (nm_dir / "SKILL.md").write_text("---\nname: evil\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 0


def test_find_skills_rglob_skips_pycache(tmp_path: Path) -> None:
    """rglob fallback must skip __pycache__."""
    pc_dir = tmp_path / "__pycache__"
    pc_dir.mkdir(parents=True)
    (pc_dir / "SKILL.md").write_text("---\nname: evil\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 0


def test_find_skills_rglob_skips_vendor(tmp_path: Path) -> None:
    """rglob fallback must skip vendor."""
    vendor_dir = tmp_path / "vendor" / "pkg"
    vendor_dir.mkdir(parents=True)
    (vendor_dir / "SKILL.md").write_text("---\nname: evil\n---\n")
    skills = find_skills_in_dir(tmp_path)
    assert len(skills) == 0


def test_find_skills_rglob_containment(tmp_path: Path) -> None:
    """rglob fallback must validate paths are within root."""
    # Create a valid skill outside root, symlinked in
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "SKILL.md").write_text("---\nname: outside-skill\n---\n")
    link = tmp_path / "sandbox" / "sneaky"
    (tmp_path / "sandbox").mkdir()
    link.symlink_to(outside)
    # The skill in the symlinked dir should be skipped
    skills = find_skills_in_dir(tmp_path / "sandbox")
    assert len(skills) == 0
