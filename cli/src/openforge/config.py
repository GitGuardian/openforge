# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from openforge.cli import get_project_dir, get_user_config_dir
from openforge.config_file import _DEFAULTS as _DEFAULTS  # pyright: ignore[reportPrivateUsage]
from openforge.config_file import get_config_value, set_config_value

config_app = typer.Typer(help="Manage OpenForge configuration.")

_console = Console()


@config_app.command("list")
def config_list() -> None:
    """Show all configuration keys with their resolved values and sources."""
    project_dir = get_project_dir()
    user_config_dir = get_user_config_dir()

    table = Table(title="Configuration")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    table.add_column("Source", style="yellow")

    for key in sorted(_DEFAULTS):
        cv = get_config_value(
            key, project_dir=project_dir, user_config_dir=user_config_dir
        )
        table.add_row(key, cv.value, cv.source)

    _console.print(table)


@config_app.command("get")
def config_get(key: str = typer.Argument(help="Configuration key to read.")) -> None:
    """Show a single configuration key's resolved value and source."""
    project_dir = get_project_dir()
    user_config_dir = get_user_config_dir()

    cv = get_config_value(
        key, project_dir=project_dir, user_config_dir=user_config_dir
    )
    _console.print(f"{key} = {cv.value}  [dim](source: {cv.source})[/dim]")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(help="Configuration key to set."),
    value: str = typer.Argument(help="Value to assign."),
) -> None:
    """Write a configuration value to the user config file."""
    user_config_dir = get_user_config_dir()
    set_config_value(key, value, user_config_dir=user_config_dir)
    _console.print(f"Set {key} = {value}")
