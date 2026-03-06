from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from openforge.cli import get_project_dir
from openforge.lock import lock_file_path, read_lock
from openforge.telemetry import send_event
from openforge.types import LockEntry

_console = Console()


def find_command(
    query: str = typer.Argument(..., help="Search query"),
    is_global: bool = typer.Option(False, "--global", "-g", help="Search globally installed"),
) -> None:
    """Search installed plugins and skills by name or skill."""
    project_dir = get_project_dir()
    lock_path = lock_file_path(project_dir, is_global=is_global)

    lock = read_lock(lock_path)

    query_lower = query.lower()
    matches: dict[str, LockEntry] = {}
    for name, entry in lock.entries.items():
        if query_lower in name.lower():
            matches[name] = entry
            continue
        for skill in entry.skills:
            if query_lower in skill.lower():
                matches[name] = entry
                break

    send_event("find", {"results_count": len(matches)})

    if not matches:
        _console.print("No results found.")
        return

    table = Table(title="Search Results")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Source", style="green")
    table.add_column("Skills", style="yellow")

    for name, entry in matches.items():
        table.add_row(
            name,
            entry.type.value,
            entry.source,
            ", ".join(entry.skills),
        )

    _console.print(table)
