from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openforge.types import ContentType, LockEntry, LockFile, SourceType


def lock_file_path(project_dir: Path, *, is_global: bool) -> Path:
    """Return the lock file path for project-local or global installs."""
    if is_global:
        from openforge.cli import get_user_config_dir

        return get_user_config_dir() / "lock.json"
    return project_dir / ".openforge-lock.json"


def _entry_to_dict(entry: LockEntry) -> dict[str, Any]:
    """Serialise a LockEntry to a plain dict, converting enums to their values."""
    return {
        "type": entry.type.value,
        "source": entry.source,
        "source_type": entry.source_type.value,
        "git_url": entry.git_url,
        "git_sha": entry.git_sha,
        "skills": list(entry.skills),
        "agents_installed": list(entry.agents_installed),
        "installed_at": entry.installed_at,
        "updated_at": entry.updated_at,
    }


def _dict_to_entry(data: dict[str, Any]) -> LockEntry:
    """Deserialise a plain dict into a LockEntry, mapping strings back to enums."""
    return LockEntry(
        type=ContentType(data["type"]),
        source=data["source"],
        source_type=SourceType(data["source_type"]),
        git_url=data["git_url"],
        git_sha=data["git_sha"],
        skills=tuple(data["skills"]),
        agents_installed=tuple(data["agents_installed"]),
        installed_at=data["installed_at"],
        updated_at=data["updated_at"],
    )


def read_lock(path: Path) -> LockFile:
    """Read a lock file from *path*, returning an empty LockFile if the file is missing."""
    if not path.exists():
        return LockFile()

    raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, LockEntry] = {
        name: _dict_to_entry(entry_data)
        for name, entry_data in raw.get("entries", {}).items()
    }
    return LockFile(version=raw.get("version", 1), entries=entries)


def write_lock(path: Path, lock: LockFile) -> None:
    """Write *lock* to *path* as formatted JSON with indent=2.

    Uses atomic write (write-to-temp-then-rename) and sets restrictive
    permissions (0o600) on the resulting file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "version": lock.version,
        "entries": {
            name: _entry_to_dict(entry)
            for name, entry in lock.entries.items()
        },
    }
    content = json.dumps(payload, indent=2) + "\n"
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, path)


def add_lock_entry(path: Path, name: str, entry: LockEntry) -> None:
    """Add or update an entry in the lock file at *path*."""
    lock = read_lock(path)
    lock.entries[name] = entry
    write_lock(path, lock)


def remove_lock_entry(path: Path, name: str) -> None:
    """Remove the entry keyed by *name* from the lock file at *path*."""
    lock = read_lock(path)
    lock.entries.pop(name, None)
    write_lock(path, lock)
