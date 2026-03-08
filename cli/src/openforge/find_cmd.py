# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from openforge.cli import get_project_dir
from openforge.lock import lock_file_path, read_lock
from openforge.providers.forge import search_forge
from openforge.telemetry import send_event
from openforge.types import LockEntry

_console = Console()


def _search_local(query: str, project_dir: Any, *, is_global: bool) -> dict[str, LockEntry]:
    """Search locally installed entries by name or skill."""
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
    return matches


def _display_local(matches: dict[str, LockEntry]) -> None:
    """Display local search results."""
    table = Table(title="Local Results")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Source", style="green")
    table.add_column("Skills", style="yellow")
    for name, entry in matches.items():
        table.add_row(name, entry.type.value, entry.source, ", ".join(entry.skills))
    _console.print(table)


def _display_remote(results: list[dict[str, Any]]) -> None:
    """Display remote Forge search results."""
    table = Table(title="Forge Results")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="green")
    table.add_column("Install", style="yellow")
    for pkg in results:
        name = str(pkg.get("name", ""))
        desc = str(pkg.get("description", ""))
        table.add_row(name, desc, f"openforge add forge:{name}")
    _console.print(table)


def find_command(
    query: str = typer.Argument(..., help="Search query"),
    is_global: bool = typer.Option(False, "--global", "-g", help="Search globally installed"),
    remote: bool = typer.Option(False, "--remote", "-r", help="Search the Forge marketplace"),
    all_sources: bool = typer.Option(False, "--all", "-a", help="Search local and remote"),
) -> None:
    """Search installed plugins and skills by name or skill."""
    project_dir = get_project_dir()
    search_remote = remote or all_sources
    search_local = not remote or all_sources

    local_matches: dict[str, LockEntry] = {}
    if search_local:
        local_matches = _search_local(query, project_dir, is_global=is_global)

    remote_results: list[dict[str, Any]] = []
    if search_remote:
        try:
            remote_results = search_forge(query)
        except Exception:  # noqa: BLE001
            _console.print("[yellow]Remote search failed. Check your connection.[/yellow]")

    total = len(local_matches) + len(remote_results)
    send_event("find", {"results_count": total})

    if total == 0:
        _console.print("No results found.")
        return

    if local_matches:
        _display_local(local_matches)

    if remote_results:
        _display_remote(remote_results)
