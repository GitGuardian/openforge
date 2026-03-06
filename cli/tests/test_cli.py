# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import typer

from openforge.cli import get_project_dir, get_user_config_dir, _build_app, main


def test_get_user_config_dir_returns_path() -> None:
    """get_user_config_dir should return a Path containing 'openforge'."""
    result = get_user_config_dir()
    assert isinstance(result, Path)
    assert "openforge" in str(result)


def test_get_project_dir_returns_cwd() -> None:
    """get_project_dir should return the current working directory."""
    result = get_project_dir()
    assert isinstance(result, Path)
    assert result == Path.cwd()


def test_build_app_returns_typer_app() -> None:
    """_build_app should return a Typer app with registered commands."""
    app = _build_app()
    assert isinstance(app, typer.Typer)


def test_build_app_registers_commands() -> None:
    """_build_app registers add, remove, list, find commands."""
    app = _build_app()
    # Typer stores registered commands internally
    # We verify by running --help which lists them
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "add" in result.output
    assert "remove" in result.output
    assert "list" in result.output
    assert "find" in result.output
    assert "config" in result.output


def test_main_calls_build_app_and_runs() -> None:
    """main() should build the app and invoke it."""
    with patch("openforge.cli._build_app") as mock_build, \
         patch("openforge.cli.app") as mock_app:
        mock_build.return_value = mock_app
        main()
        mock_build.assert_called_once()
        mock_app.assert_called_once()
