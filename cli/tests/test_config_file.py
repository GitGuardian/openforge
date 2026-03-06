# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from openforge.config_file import load_config, get_config_value, set_config_value


def test_load_defaults(tmp_path: Path) -> None:
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.forge_url == "https://openforge.gitguardian.com"
    assert config.telemetry_enabled is True


def test_user_config_overrides_defaults(tmp_path: Path) -> None:
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "config.toml").write_text('[forge]\nurl = "https://forge.acme.com"\n')
    config = load_config(project_dir=tmp_path, user_config_dir=user_dir)
    assert config.forge_url == "https://forge.acme.com"


def test_project_config_overrides_user(tmp_path: Path) -> None:
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "config.toml").write_text('[forge]\nurl = "https://user.com"\n')
    (tmp_path / ".openforge.toml").write_text('[forge]\nurl = "https://project.com"\n')
    config = load_config(project_dir=tmp_path, user_config_dir=user_dir)
    assert config.forge_url == "https://project.com"


def test_env_var_overrides_all(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / ".openforge.toml").write_text('[forge]\nurl = "https://project.com"\n')
    monkeypatch.setenv("OPENFORGE_FORGE_URL", "https://env.com")
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.forge_url == "https://env.com"


def test_do_not_track_disables_telemetry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DO_NOT_TRACK", "1")
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.telemetry_enabled is False


def test_ci_env_disables_telemetry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.telemetry_enabled is False


def test_get_config_value(tmp_path: Path) -> None:
    (tmp_path / ".openforge.toml").write_text('[forge]\nurl = "https://project.com"\n')
    val = get_config_value("forge.url", project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert val.value == "https://project.com"
    assert val.source == "project"


def test_get_config_value_default(tmp_path: Path) -> None:
    val = get_config_value("forge.url", project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert val.value == "https://openforge.gitguardian.com"
    assert val.source == "default"


def test_get_config_value_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENFORGE_FORGE_URL", "https://env.com")
    val = get_config_value("forge.url", project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert val.value == "https://env.com"
    assert val.source == "env"


def test_set_config_value(tmp_path: Path) -> None:
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    set_config_value("forge.url", "https://new.com", user_config_dir=user_dir)
    content = (user_dir / "config.toml").read_text()
    assert "https://new.com" in content


def test_set_config_value_creates_dir(tmp_path: Path) -> None:
    user_dir = tmp_path / "nested" / "user"
    set_config_value("forge.url", "https://new.com", user_config_dir=user_dir)
    content = (user_dir / "config.toml").read_text()
    assert "https://new.com" in content


def test_set_config_value_boolean_roundtrip(tmp_path: Path) -> None:
    """Setting telemetry.enabled to 'true' should store a TOML boolean, not a string."""
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    set_config_value("telemetry.enabled", "true", user_config_dir=user_dir)

    # Read back via get_config_value
    val = get_config_value(
        "telemetry.enabled",
        project_dir=tmp_path,
        user_config_dir=user_dir,
    )
    assert val.value == "true"
    assert val.source == "user"

    # Also verify the TOML file contains a real boolean, not a quoted string
    content = (user_dir / "config.toml").read_text()
    # TOML boolean: `enabled = true` (no quotes)
    assert "enabled = true" in content
    # Must NOT be a quoted string: `enabled = "true"`
    assert 'enabled = "true"' not in content


def test_set_config_value_boolean_false_roundtrip(tmp_path: Path) -> None:
    """Setting telemetry.enabled to 'false' should store a TOML boolean."""
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    set_config_value("telemetry.enabled", "false", user_config_dir=user_dir)

    val = get_config_value(
        "telemetry.enabled",
        project_dir=tmp_path,
        user_config_dir=user_dir,
    )
    assert val.value == "false"

    content = (user_dir / "config.toml").read_text()
    assert "enabled = false" in content
    assert 'enabled = "false"' not in content


def test_set_config_value_rejects_unknown_key(tmp_path: Path) -> None:
    """set_config_value must reject keys not in _DEFAULTS."""
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    with pytest.raises(ValueError, match="Unknown config key"):
        set_config_value("bogus.key", "evil", user_config_dir=user_dir)
