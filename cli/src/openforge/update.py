# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import datetime
import tempfile
from pathlib import Path

import typer
from rich.console import Console

from openforge.add import get_provider
from openforge.check import check_entry_staleness
from openforge.cli import get_project_dir
from openforge.installer import create_canonical_storage, install_to_all_agents
from openforge.lock import add_lock_entry, lock_file_path, read_lock
from openforge.plugins import detect_content
from openforge.providers.source_parser import parse_source
from openforge.types import ContentType, LockEntry, SkillInfo

_console = Console()


def _reinstall_entry(name: str, entry: LockEntry, project_dir: Path, is_global: bool) -> None:
    """Re-run the add flow for a single outdated entry."""
    source = parse_source(entry.source)
    provider = get_provider(source)

    with tempfile.TemporaryDirectory(prefix="openforge-") as tmp_str:
        tmp_dir = Path(tmp_str)
        fetch_result = provider.fetch(source, tmp_dir)
        new_sha = fetch_result.sha
        content_root = fetch_result.content_root
        detected = detect_content(content_root)

        # Show what changed
        old_skills = set(entry.skills)
        new_skills = {s.name for s in detected.skills}
        added = new_skills - old_skills
        removed = old_skills - new_skills
        if added:
            _console.print(
                f"  [green]+ {len(added)} new skills: {', '.join(sorted(added))}[/green]"
            )
        if removed:
            _console.print(
                f"  [red]- {len(removed)} removed skills: {', '.join(sorted(removed))}[/red]"
            )
        if not added and not removed:
            _console.print("  [dim]Content updated (no skill changes)[/dim]")

        # Reinstall skills to canonical storage
        canonical_skills: list[SkillInfo] = []
        for skill in detected.skills:
            skill_source_dir = content_root / skill.path if skill.path else content_root
            canonical_dest = create_canonical_storage(
                source_dir=skill_source_dir,
                project_dir=project_dir,
                name=skill.name,
                content_type=ContentType.SKILL,
                is_global=is_global,
            )
            canonical_skills.append(
                SkillInfo(
                    name=skill.name,
                    description=skill.description,
                    tags=skill.tags,
                    path=str(canonical_dest),
                )
            )

        agents = install_to_all_agents(
            skills=canonical_skills,
            project_dir=project_dir,
            content_type=ContentType.SKILL,
            is_global=is_global,
            target_agent=None,
        )

        # Update lock entry
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        new_entry = LockEntry(
            type=entry.type,
            source=entry.source,
            source_type=entry.source_type,
            git_url=entry.git_url,
            git_sha=new_sha,
            skills=tuple(s.name for s in detected.skills),
            agents_installed=tuple(agents),
            installed_at=entry.installed_at,
            updated_at=now,
        )
        lock_path = lock_file_path(project_dir, is_global=is_global)
        add_lock_entry(lock_path, name, new_entry)


def update_command(
    name: str | None = typer.Argument(None, help="Update a specific entry (default: all)"),
    is_global: bool = typer.Option(False, "--global", "-g", help="Update globally installed"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-confirm"),
) -> None:
    """Update outdated plugins and skills."""
    project_dir = get_project_dir()
    path = lock_file_path(project_dir, is_global=is_global)
    lock = read_lock(path)

    if not lock.entries:
        _console.print("[yellow]No installed plugins or skills.[/yellow]")
        raise typer.Exit()

    if name and name not in lock.entries:
        _console.print(f"[red]Not found: {name!r}[/red]")
        raise typer.Exit(code=1)

    entries = {name: lock.entries[name]} if name else lock.entries

    # Check staleness
    outdated: list[tuple[str, LockEntry]] = []
    for entry_name, entry in entries.items():
        result = check_entry_staleness(entry_name, entry)
        if result.is_outdated:
            outdated.append((entry_name, entry))

    if not outdated:
        _console.print("[green]All up to date.[/green]")
        raise typer.Exit()

    _console.print(f"[yellow]{len(outdated)} outdated:[/yellow]")
    for entry_name, _ in outdated:
        _console.print(f"  - {entry_name}")

    if not yes:
        confirm = typer.confirm("Update all?")
        if not confirm:
            raise typer.Exit()

    for entry_name, entry in outdated:
        _console.print(f"\n[bold]Updating {entry_name}...[/bold]")
        _reinstall_entry(entry_name, entry, project_dir, is_global)
        _console.print(f"[green]Updated {entry_name}[/green]")

    _console.print(f"\n[green]Updated {len(outdated)} entries.[/green]")
