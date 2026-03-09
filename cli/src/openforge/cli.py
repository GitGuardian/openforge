# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import typer
from platformdirs import user_config_dir

app = typer.Typer(name="openforge", help="Install and manage AI agent plugins and skills.")


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version

        typer.echo(version("openforge"))
        raise typer.Exit()


@app.callback()
def _main(  # pyright: ignore[reportUnusedFunction]
    version: bool | None = typer.Option(  # noqa: UP007
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """Install and manage AI agent plugins and skills."""


def get_project_dir() -> Path:
    """Return the current project directory."""
    return Path.cwd()


def get_user_config_dir() -> Path:
    """Return the user-level config directory (platform-appropriate)."""
    return Path(user_config_dir("openforge"))


def _build_app() -> typer.Typer:
    """Register all commands and return the app. Lazy to avoid circular imports."""
    from openforge.add import add_command
    from openforge.auth import auth_app
    from openforge.check import check_command
    from openforge.config import config_app
    from openforge.find_cmd import find_command
    from openforge.list_cmd import list_command
    from openforge.publish import publish_command
    from openforge.remove import remove_command
    from openforge.update import update_command

    app.command("add")(add_command)
    app.command("remove")(remove_command)
    app.command("list")(list_command)
    app.command("find")(find_command)
    app.command("check")(check_command)
    app.command("update")(update_command)
    app.command("publish")(publish_command)
    app.add_typer(auth_app, name="auth")
    app.add_typer(config_app, name="config")
    return app


def main() -> None:
    """Entry point for the CLI."""
    _build_app()
    app()
