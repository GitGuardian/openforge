# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """A temporary project directory with .agents/ structure."""
    agents = tmp_path / ".agents"
    (agents / "plugins").mkdir(parents=True)
    (agents / "skills").mkdir(parents=True)
    return tmp_path


@pytest.fixture
def sample_skill_repo(tmp_path: Path) -> Path:
    """A temporary directory mimicking a GitHub repo with skills."""
    repo = tmp_path / "repo"
    skills = repo / "skills"
    for name in ["lint", "format", "test"]:
        skill_dir = skills / name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {name.title()} your code\ntags:\n  - quality\n---\n"
        )
    return repo


@pytest.fixture
def sample_plugin_repo(tmp_path: Path) -> Path:
    """A temporary directory mimicking a GitHub repo with a plugin."""
    repo = tmp_path / "repo"
    repo.mkdir()

    plugin_dir = repo / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "test-plugin", "description": "A test plugin"})
    )

    skills_dir = repo / "skills" / "skill-a"
    skills_dir.mkdir(parents=True)
    (skills_dir / "SKILL.md").write_text("---\nname: skill-a\n---\n")

    commands_dir = repo / "commands"
    commands_dir.mkdir()
    (commands_dir / "deploy.md").write_text("# Deploy\nDeploy things.")

    (repo / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"test": {"command": "echo"}}})
    )

    return repo
