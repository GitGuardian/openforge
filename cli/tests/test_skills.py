from __future__ import annotations

from pathlib import Path

from openforge.skills import parse_skill_md, find_skills_in_dir


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
