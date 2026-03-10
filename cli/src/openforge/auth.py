# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, cast

import typer
from platformdirs import user_config_dir
from rich.console import Console

auth_app = typer.Typer(help="Manage authentication with The Forge.")

_console = Console()


def _get_token_dir() -> Path:
    """Return the directory for storing auth tokens."""
    return Path(user_config_dir("openforge"))


def _token_path() -> Path:
    """Return the path to the token file."""
    return _get_token_dir() / "token.json"


def _sign_in_with_password(email: str, password: str, forge_url: str) -> Any:
    """Authenticate with the Forge's Supabase Auth endpoint.

    Returns an object with .session.access_token, .session.refresh_token,
    .user.email, .user.id on success.
    Raises ValueError on auth failure.
    """
    import httpx

    # POST to Supabase GoTrue endpoint via the Forge proxy
    response = httpx.post(
        f"{forge_url}/auth/v1/token?grant_type=password",
        json={"email": email, "password": password},
        headers={"Content-Type": "application/json"},
        timeout=10.0,
    )

    if response.status_code != 200:
        data = response.json()
        msg = data.get("error_description") or data.get("msg") or "Authentication failed"
        raise ValueError(msg)

    data: dict[str, Any] = response.json()
    user_data: dict[str, Any] = data.get("user", {})

    from types import SimpleNamespace

    session = SimpleNamespace(
        access_token=str(data["access_token"]),
        refresh_token=str(data["refresh_token"]),
    )
    user = SimpleNamespace(
        email=str(user_data.get("email", email)),
        id=str(user_data.get("id", "")),
    )
    return SimpleNamespace(session=session, user=user)


def _store_token(
    access_token: str,
    refresh_token: str,
    email: str,
    user_id: str,
) -> None:
    """Write token data to disk with restrictive permissions."""
    token_dir = _get_token_dir()
    os.makedirs(token_dir, mode=0o700, exist_ok=True)

    token_file = token_dir / "token.json"
    token_data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "email": email,
        "user_id": user_id,
    }
    token_file.write_text(json.dumps(token_data), encoding="utf-8")
    os.chmod(token_file, 0o600)


def _read_token() -> dict[str, str] | None:
    """Read stored token data, or return None if not found."""
    token_file = _token_path()
    if not token_file.is_file():
        return None
    try:
        data: Any = json.loads(token_file.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "access_token" in data:
            typed_data = cast(dict[str, Any], data)
            return {str(k): str(v) for k, v in typed_data.items()}
    except (json.JSONDecodeError, OSError):
        pass
    return None


def get_auth_token() -> str | None:
    """Return stored access token, or None if not logged in."""
    token_data = _read_token()
    if token_data is None:
        return None
    return token_data.get("access_token")


@auth_app.command("login")
def login_command() -> None:
    """Log in to The Forge with email and password."""
    from openforge.config_file import load_config

    email = typer.prompt("Email")
    password = typer.prompt("Password", hide_input=True)

    config = load_config()
    supabase_url = config.supabase_url

    try:
        result = _sign_in_with_password(email, password, supabase_url)
    except ValueError as e:
        _console.print(f"[red]Login failed: {e}[/red]")
        raise typer.Exit(code=1) from None

    _store_token(
        access_token=result.session.access_token,
        refresh_token=result.session.refresh_token,
        email=result.user.email,
        user_id=result.user.id,
    )

    _console.print(f"[green]Logged in as {result.user.email}[/green]")


@auth_app.command("logout")
def logout_command() -> None:
    """Log out and remove stored credentials."""
    token_file = _token_path()
    if token_file.is_file():
        token_file.unlink()
        _console.print("[green]Logged out.[/green]")
    else:
        _console.print("Not logged in.")


@auth_app.command("status")
def status_command() -> None:
    """Show current authentication status."""
    token_data = _read_token()
    if token_data is None:
        _console.print("Not logged in. Run [bold]openforge auth login[/bold] to authenticate.")
        return

    email = token_data.get("email", "unknown")
    _console.print(f"Logged in as [bold]{email}[/bold]")
