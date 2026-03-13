# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import re

import httpx
import typer
from rich.console import Console

from openforge.api_client import ForgeAPIError, ForgeClient
from openforge.auth import get_auth_token

_console = Console()

_GIT_URL_PATTERN = re.compile(r"^https://(github\.com|gitlab\.com)/[\w.-]+/[\w.-]+(\.git)?$")


def publish_command(
    git_url: str = typer.Argument(..., help="GitHub or GitLab repository URL"),
    description: str | None = typer.Option(
        None, "--description", "-d", help="Brief description of the plugin"
    ),
) -> None:
    """Submit a plugin to The Forge for review."""
    token = get_auth_token()
    if not token:
        _console.print("[red]Not logged in. Run [bold]openforge auth login[/bold] first.[/red]")
        raise typer.Exit(code=1)

    if not _GIT_URL_PATTERN.match(git_url):
        _console.print(
            "[red]Invalid URL. Must be a GitHub or GitLab repository URL "
            "(e.g. https://github.com/owner/repo).[/red]"
        )
        raise typer.Exit(code=1)

    client = ForgeClient(token=token)

    try:
        result = client.submit(git_url, description)
    except ForgeAPIError as e:
        _console.print(f"[red]Submission failed: {e}[/red]")
        raise typer.Exit(code=1) from None
    except httpx.TransportError:
        _console.print("[red]Could not connect to The Forge. Check your network.[/red]")
        raise typer.Exit(code=1) from None

    status = result.get("status", "unknown")
    _console.print(f"[green]Submission created![/green] Status: {status}")
