# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from openforge.cli import get_project_dir
from openforge.lock import lock_file_path, read_lock

_console = Console()


def list_command(
    is_global: bool = typer.Option(False, "--global", "-g", help="List globally installed"),
    agent: str | None = typer.Option(None, "--agent", "-a", help="Filter by agent"),
) -> None:
    """List installed plugins and skills."""
    project_dir = get_project_dir()
    lock_path = lock_file_path(project_dir, is_global=is_global)

    lock = read_lock(lock_path)

    if not lock.entries:
        _console.print("No plugins or skills installed.")
        return

    # Apply agent filter if requested
    filtered_names: list[str] = []
    for name, entry in lock.entries.items():
        if agent is not None and agent not in entry.agents_installed:
            continue
        filtered_names.append(name)

    if not filtered_names:
        _console.print(f"No plugins or skills installed for agent '{agent}'.")
        return

    table = Table(title="Installed Plugins & Skills")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Source", style="green")
    table.add_column("Skills", style="yellow")
    table.add_column("Agents", style="blue")

    for name in filtered_names:
        entry = lock.entries[name]
        table.add_row(
            name,
            entry.type.value,
            entry.source,
            ", ".join(entry.skills),
            ", ".join(entry.agents_installed),
        )

    _console.print(table)
