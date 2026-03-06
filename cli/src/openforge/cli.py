from __future__ import annotations

from pathlib import Path

import typer
from platformdirs import user_config_dir

app = typer.Typer(name="openforge", help="Install and manage AI agent plugins and skills.")


def get_project_dir() -> Path:
    """Return the current project directory."""
    return Path.cwd()


def get_user_config_dir() -> Path:
    """Return the user-level config directory (platform-appropriate)."""
    return Path(user_config_dir("openforge"))


def _build_app() -> typer.Typer:
    """Register all commands and return the app. Lazy to avoid circular imports."""
    from openforge.add import add_command
    from openforge.remove import remove_command
    from openforge.list_cmd import list_command
    from openforge.find_cmd import find_command
    from openforge.config import config_app

    app.command("add")(add_command)
    app.command("remove")(remove_command)
    app.command("list")(list_command)
    app.command("find")(find_command)
    app.add_typer(config_app, name="config")
    return app


def main() -> None:
    """Entry point for the CLI."""
    _build_app()
    app()
