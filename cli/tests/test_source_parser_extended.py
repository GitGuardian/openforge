# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from openforge.providers.source_parser import parse_source
from openforge.types import SourceType


# GitLab URLs
def test_parse_gitlab_url() -> None:
    s = parse_source("https://gitlab.com/acme/skills")
    assert s.source_type == SourceType.GITLAB
    assert s.url == "https://gitlab.com/acme/skills"


def test_parse_gitlab_subgroup() -> None:
    s = parse_source("https://gitlab.com/group/subgroup/repo")
    assert s.source_type == SourceType.GITLAB
    assert s.url == "https://gitlab.com/group/subgroup/repo"


def test_parse_gitlab_prefix() -> None:
    s = parse_source("gitlab:acme/skills")
    assert s.source_type == SourceType.GITLAB
    assert s.url == "https://gitlab.com/acme/skills"


# SSH URLs
def test_parse_ssh_url() -> None:
    s = parse_source("git@github.com:acme/skills.git")
    assert s.source_type == SourceType.GIT
    assert s.url == "git@github.com:acme/skills.git"


def test_parse_ssh_gitlab() -> None:
    s = parse_source("git@gitlab.com:acme/skills.git")
    assert s.source_type == SourceType.GIT
    assert s.url == "git@gitlab.com:acme/skills.git"


# Local paths
def test_parse_local_relative() -> None:
    s = parse_source("./my-plugin")
    assert s.source_type == SourceType.LOCAL
    assert s.local_path == "./my-plugin"


def test_parse_local_absolute() -> None:
    s = parse_source("/tmp/my-plugin")
    assert s.source_type == SourceType.LOCAL
    assert s.local_path == "/tmp/my-plugin"


def test_parse_local_parent() -> None:
    s = parse_source("../my-plugin")
    assert s.source_type == SourceType.LOCAL
    assert s.local_path == "../my-plugin"


# Branch refs
def test_parse_github_with_branch() -> None:
    s = parse_source("acme/skills#develop")
    assert s.source_type == SourceType.GITHUB
    assert s.owner == "acme"
    assert s.repo == "skills"
    assert s.ref == "develop"


def test_parse_github_with_skill_and_branch() -> None:
    s = parse_source("acme/skills@my-skill#v2")
    assert s.source_type == SourceType.GITHUB
    assert s.skill_name == "my-skill"
    assert s.ref == "v2"


# Well-known
def test_parse_well_known_url() -> None:
    s = parse_source("https://mintlify.com/docs")
    assert s.source_type == SourceType.WELL_KNOWN
    assert s.url == "https://mintlify.com/docs"


# Forge
def test_parse_forge_prefix() -> None:
    s = parse_source("forge:my-plugin")
    assert s.source_type == SourceType.FORGE
    assert s.url == "my-plugin"
