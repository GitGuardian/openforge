from __future__ import annotations

import json
from pathlib import Path

from openforge.lock import read_lock, write_lock, add_lock_entry, remove_lock_entry
from openforge.types import LockFile, LockEntry, ContentType, SourceType


def test_read_lock_missing_file(tmp_path: Path) -> None:
    lock = read_lock(tmp_path / ".openforge-lock.json")
    assert lock.version == 1
    assert lock.entries == {}


def test_write_and_read_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.SKILL,
        source="acme/tools@lint",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/tools",
        git_sha="abc123",
        skills=["lint"],
        agents_installed=["claude-code"],
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    lock = LockFile(entries={"lint": entry})
    write_lock(lock_path, lock)

    loaded = read_lock(lock_path)
    assert "lint" in loaded.entries
    assert loaded.entries["lint"].git_sha == "abc123"
    assert loaded.entries["lint"].type == ContentType.SKILL


def test_add_lock_entry(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.PLUGIN,
        source="acme/plugin",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/plugin",
        git_sha="def456",
        skills=["skill-a", "skill-b"],
        agents_installed=["claude-code", "cursor"],
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    add_lock_entry(lock_path, "my-plugin", entry)
    lock = read_lock(lock_path)
    assert "my-plugin" in lock.entries


def test_remove_lock_entry(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.SKILL,
        source="acme/tools@lint",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/tools",
        git_sha="abc123",
        skills=["lint"],
        agents_installed=["claude-code"],
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"lint": entry}))
    remove_lock_entry(lock_path, "lint")
    lock = read_lock(lock_path)
    assert "lint" not in lock.entries


def test_lock_file_json_format(tmp_path: Path) -> None:
    lock_path = tmp_path / ".openforge-lock.json"
    entry = LockEntry(
        type=ContentType.PLUGIN,
        source="acme/plugin",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/plugin",
        git_sha="abc123",
        skills=["skill-a"],
        agents_installed=["claude-code"],
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"my-plugin": entry}))
    raw = json.loads(lock_path.read_text())
    assert raw["version"] == 1
    assert raw["entries"]["my-plugin"]["type"] == "plugin"
    assert raw["entries"]["my-plugin"]["source_type"] == "github"
