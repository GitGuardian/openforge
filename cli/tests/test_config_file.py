# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path

import pytest

from openforge.config_file import get_config_value, load_config, set_config_value


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


# ---------------------------------------------------------------------------
# supabase_url config tests
# ---------------------------------------------------------------------------


def test_supabase_url_defaults_to_forge_url(tmp_path: Path) -> None:
    """When no supabase.url is set, supabase_url falls back to forge_url."""
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.supabase_url == config.forge_url


def test_supabase_url_from_user_config(tmp_path: Path) -> None:
    """supabase_url reads from user config file."""
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "config.toml").write_text('[supabase]\nurl = "http://localhost:54321"\n')
    config = load_config(project_dir=tmp_path, user_config_dir=user_dir)
    assert config.supabase_url == "http://localhost:54321"


def test_supabase_url_from_project_config(tmp_path: Path) -> None:
    """supabase_url from project config overrides user config."""
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "config.toml").write_text('[supabase]\nurl = "http://user-supabase:54321"\n')
    (tmp_path / ".openforge.toml").write_text('[supabase]\nurl = "http://project-supabase:54321"\n')
    config = load_config(project_dir=tmp_path, user_config_dir=user_dir)
    assert config.supabase_url == "http://project-supabase:54321"


def test_supabase_url_env_var_overrides_all(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OPENFORGE_SUPABASE_URL env var overrides all config layers."""
    (tmp_path / ".openforge.toml").write_text('[supabase]\nurl = "http://project:54321"\n')
    monkeypatch.setenv("OPENFORGE_SUPABASE_URL", "http://env-supabase:54321")
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.supabase_url == "http://env-supabase:54321"


def test_supabase_url_env_var_SUPABASE_URL(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SUPABASE_URL env var is also respected (common Supabase convention)."""
    monkeypatch.setenv("SUPABASE_URL", "http://supabase-env:54321")
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.supabase_url == "http://supabase-env:54321"


def test_OPENFORGE_SUPABASE_URL_overrides_SUPABASE_URL(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """OPENFORGE_SUPABASE_URL takes precedence over SUPABASE_URL."""
    monkeypatch.setenv("SUPABASE_URL", "http://generic:54321")
    monkeypatch.setenv("OPENFORGE_SUPABASE_URL", "http://specific:54321")
    config = load_config(project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert config.supabase_url == "http://specific:54321"


def test_get_config_value_supabase_url(tmp_path: Path) -> None:
    """get_config_value works for supabase.url key."""
    (tmp_path / ".openforge.toml").write_text('[supabase]\nurl = "http://local:54321"\n')
    val = get_config_value("supabase.url", project_dir=tmp_path, user_config_dir=tmp_path / "user")
    assert val.value == "http://local:54321"
    assert val.source == "project"


def test_set_config_value_supabase_url(tmp_path: Path) -> None:
    """set_config_value accepts supabase.url."""
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    set_config_value("supabase.url", "http://my-supabase:54321", user_config_dir=user_dir)
    content = (user_dir / "config.toml").read_text()
    assert "http://my-supabase:54321" in content


def test_set_config_value_atomic_write(tmp_path: Path) -> None:
    """Config file must be written atomically — os.chmod must NOT be used."""
    import os
    from unittest.mock import patch

    user_dir = tmp_path / "user"
    user_dir.mkdir()

    chmod_calls: list[object] = []
    original_chmod = os.chmod

    def spy_chmod(*args: object) -> None:
        chmod_calls.append(args)
        original_chmod(*args)  # type: ignore[arg-type]

    with patch("openforge.config_file.os.chmod", side_effect=spy_chmod):
        set_config_value("forge.url", "https://new.com", user_config_dir=user_dir)

    config_path = user_dir / "config.toml"
    assert config_path.exists()
    mode = os.stat(config_path).st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
    # os.chmod must NOT be called — permissions set at creation via os.open
    assert len(chmod_calls) == 0, "os.chmod should not be called; use os.open with mode instead"


def test_malformed_toml_gives_clear_error(tmp_path: Path) -> None:
    """Corrupt TOML should raise ValueError, not raw TOMLDecodeError."""
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "config.toml").write_text("[invalid toml", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid TOML"):
        load_config(project_dir=tmp_path, user_config_dir=user_dir)
