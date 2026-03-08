# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import subprocess  # nosec B404
from dataclasses import dataclass

import typer
from rich.console import Console
from rich.table import Table

from openforge.cli import get_project_dir
from openforge.lock import lock_file_path, read_lock
from openforge.telemetry import send_event
from openforge.types import LockEntry, SourceType

_console = Console()


@dataclass(frozen=True)
class CheckResult:
    """Result of checking a single lock entry for staleness."""

    name: str
    local_sha: str
    remote_sha: str
    is_outdated: bool
    error: str | None = None


def _git_ls_remote(git_url: str, ref: str | None = None) -> str:
    """Get remote HEAD SHA without cloning."""
    target = ref or "HEAD"
    result = subprocess.run(  # nosec B603 B607
        ["git", "ls-remote", git_url, target],
        check=True,
        capture_output=True,
        text=True,
    )
    # Output format: "sha\tref\n"
    line = result.stdout.strip().split("\n")[0]
    if not line:
        msg = f"no ref found for {target}"
        raise ValueError(msg)
    return line.split("\t")[0]


def check_entry_staleness(name: str, entry: LockEntry) -> CheckResult:
    """Check if a single lock entry is outdated."""
    if entry.source_type == SourceType.LOCAL:
        return CheckResult(
            name=name,
            local_sha="",
            remote_sha="",
            is_outdated=False,
            error="local sources cannot be checked",
        )
    if entry.source_type == SourceType.WELL_KNOWN:
        return CheckResult(
            name=name,
            local_sha="",
            remote_sha="",
            is_outdated=False,
            error="well-known sources: check not yet supported",
        )

    try:
        remote_sha = _git_ls_remote(entry.git_url)
    except (subprocess.CalledProcessError, ValueError) as exc:
        return CheckResult(
            name=name,
            local_sha=entry.git_sha,
            remote_sha="",
            is_outdated=False,
            error=str(exc),
        )

    return CheckResult(
        name=name,
        local_sha=entry.git_sha,
        remote_sha=remote_sha,
        is_outdated=entry.git_sha != remote_sha,
    )


def check_command(
    name: str | None = typer.Argument(None, help="Check a specific entry (default: all)"),
    is_global: bool = typer.Option(False, "--global", "-g", help="Check globally installed"),
) -> None:
    """Check installed plugins and skills for updates."""
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

    results: list[CheckResult] = []
    for entry_name, entry in entries.items():
        results.append(check_entry_staleness(entry_name, entry))

    # Display table
    table = Table(title="Update Check")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Installed")
    table.add_column("Remote")

    outdated_count = 0
    for r in results:
        if r.error:
            table.add_row(r.name, f"[yellow]error: {r.error}[/yellow]", "", "")
        elif r.is_outdated:
            outdated_count += 1
            table.add_row(r.name, "[red]outdated[/red]", r.local_sha[:8], r.remote_sha[:8])
        else:
            table.add_row(r.name, "[green]up to date[/green]", r.local_sha[:8], r.remote_sha[:8])

    _console.print(table)

    if outdated_count:
        _console.print(
            f"\n[yellow]{outdated_count} outdated. Run 'openforge update' to update.[/yellow]"
        )
    else:
        _console.print("\n[green]All up to date.[/green]")

    send_event("check", {"entries_checked": len(results), "outdated": outdated_count})
