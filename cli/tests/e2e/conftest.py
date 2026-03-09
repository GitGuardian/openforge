# SPDX-License-Identifier: Apache-2.0
"""Fixtures for CLI end-to-end smoke tests."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Protocol

import pytest


class RunOpenforge(Protocol):
    """Type for the run_openforge fixture callable."""

    def __call__(
        self,
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]: ...


@pytest.fixture
def run_openforge(tmp_path: Path) -> RunOpenforge:
    """Run openforge CLI as a real subprocess. Returns a helper function."""

    def _run(
        *args: str,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        cmd = ["uv", "run", "openforge", *args]
        run_env = {**os.environ, **(env or {})}
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd or tmp_path,
            timeout=30,
            env=run_env,
        )

    return _run


@pytest.fixture
def local_skill_repo(tmp_path: Path) -> Path:
    """A local directory with a single skill, for subprocess add tests."""
    repo = tmp_path / "test-repo"
    skill_dir = repo / "skills" / "test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: A test skill\ntags:\n  - test\n---\n"
    )
    return repo


@pytest.fixture
def local_plugin_repo(tmp_path: Path) -> Path:
    """A local directory with a plugin, for subprocess add tests."""
    repo = tmp_path / "test-plugin-repo"
    repo.mkdir()

    plugin_dir = repo / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text(
        json.dumps({"name": "test-plugin", "description": "A test plugin"})
    )

    skill_dir = repo / "skills" / "helper"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: helper\ndescription: Helper\n---\n")

    return repo
