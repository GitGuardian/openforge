# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from unittest.mock import patch

from openforge.lock import add_lock_entry, read_lock, remove_lock_entry, write_lock
from openforge.types import ContentType, LockEntry, LockFile, SourceType


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
        skills=("lint",),
        agents_installed=("claude-code",),
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
        skills=("skill-a", "skill-b"),
        agents_installed=("claude-code", "cursor"),
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
        skills=("lint",),
        agents_installed=("claude-code",),
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
        skills=("skill-a",),
        agents_installed=("claude-code",),
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )
    write_lock(lock_path, LockFile(entries={"my-plugin": entry}))
    raw = json.loads(lock_path.read_text())
    assert raw["version"] == 1
    assert raw["entries"]["my-plugin"]["type"] == "plugin"
    assert raw["entries"]["my-plugin"]["source_type"] == "github"


def _make_entry() -> LockEntry:
    return LockEntry(
        type=ContentType.SKILL,
        source="acme/tools@lint",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/acme/tools",
        git_sha="abc123",
        skills=("lint",),
        agents_installed=("claude-code",),
        installed_at="2026-03-06T12:00:00Z",
        updated_at="2026-03-06T12:00:00Z",
    )


def test_write_lock_creates_parent_directories(tmp_path: Path) -> None:
    """write_lock should create intermediate parent directories automatically."""
    lock_path = tmp_path / "a" / "b" / "c" / "lock.json"
    lock = LockFile(entries={"lint": _make_entry()})
    write_lock(lock_path, lock)

    assert lock_path.exists()
    loaded = read_lock(lock_path)
    assert "lint" in loaded.entries


def test_write_lock_sets_restrictive_permissions(tmp_path: Path) -> None:
    """On Unix, the lock file should have 0o600 permissions."""
    if sys.platform == "win32":
        return
    lock_path = tmp_path / "lock.json"
    lock = LockFile(entries={"lint": _make_entry()})
    write_lock(lock_path, lock)

    mode = stat.S_IMODE(os.stat(lock_path).st_mode)
    assert mode == 0o600


def test_write_lock_atomic_no_corrupt_on_failure(tmp_path: Path) -> None:
    """If writing the temp file fails, the original lock file should be untouched."""
    lock_path = tmp_path / "lock.json"
    original_entry = _make_entry()
    lock = LockFile(entries={"original": original_entry})
    write_lock(lock_path, lock)

    # Now attempt a write that will fail during os.replace
    bad_entry = LockEntry(
        type=ContentType.PLUGIN,
        source="evil/plugin",
        source_type=SourceType.GITHUB,
        git_url="https://github.com/evil/plugin",
        git_sha="bad000",
        skills=(),
        agents_installed=(),
        installed_at="2026-03-06T13:00:00Z",
        updated_at="2026-03-06T13:00:00Z",
    )
    bad_lock = LockFile(entries={"evil": bad_entry})
    with patch("openforge.lock.os.replace", side_effect=OSError("disk full")):
        try:
            write_lock(lock_path, bad_lock)
        except OSError:
            pass

    # Original file should be intact
    loaded = read_lock(lock_path)
    assert "original" in loaded.entries
    assert "evil" not in loaded.entries
