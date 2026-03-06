# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import typer
from typer.testing import CliRunner

runner = CliRunner()


def test_config_list(tmp_path: Path) -> None:
    from openforge.config import config_app

    test_app = typer.Typer()
    test_app.add_typer(config_app, name="config")

    with patch("openforge.config.get_user_config_dir", return_value=tmp_path / "user"), \
         patch("openforge.config.get_project_dir", return_value=tmp_path):
        result = runner.invoke(test_app, ["config", "list"])
        assert result.exit_code == 0
        assert "forge.url" in result.output


def test_config_get(tmp_path: Path) -> None:
    from openforge.config import config_app

    test_app = typer.Typer()
    test_app.add_typer(config_app, name="config")

    with patch("openforge.config.get_user_config_dir", return_value=tmp_path / "user"), \
         patch("openforge.config.get_project_dir", return_value=tmp_path):
        result = runner.invoke(test_app, ["config", "get", "forge.url"])
        assert result.exit_code == 0
        assert "openforge.gitguardian.com" in result.output


def test_config_set(tmp_path: Path) -> None:
    from openforge.config import config_app

    test_app = typer.Typer()
    test_app.add_typer(config_app, name="config")

    user_dir = tmp_path / "user"
    user_dir.mkdir()
    with patch("openforge.config.get_user_config_dir", return_value=user_dir):
        result = runner.invoke(test_app, ["config", "set", "forge.url", "https://new.com"])
        assert result.exit_code == 0

    content = (user_dir / "config.toml").read_text()
    assert "https://new.com" in content
