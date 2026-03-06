# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

from openforge.cli import get_user_config_dir


def test_get_user_config_dir_returns_path() -> None:
    """get_user_config_dir should return a Path containing 'openforge'."""
    result = get_user_config_dir()
    assert isinstance(result, Path)
    assert "openforge" in str(result)
