# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # pyright: ignore[reportMissingImports]

from platformdirs import user_config_dir

# ---------------------------------------------------------------------------
# CI environment variables that signal a CI environment (disables telemetry)
# ---------------------------------------------------------------------------
_CI_ENV_VARS: tuple[str, ...] = (
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "JENKINS_URL",
    "CIRCLECI",
    "TRAVIS",
    "BUILDKITE",
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Config:
    """Resolved configuration values."""

    forge_url: str = "https://openforge.gitguardian.com"
    telemetry_enabled: bool = True


@dataclass(frozen=True)
class ConfigValue:
    """A single configuration value together with the layer it came from."""

    value: str
    source: str  # "default", "user", "project", "env"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DEFAULTS: dict[str, str] = {
    "forge.url": "https://openforge.gitguardian.com",
    "telemetry.enabled": "true",
}


def _default_user_config_dir() -> Path:
    return Path(user_config_dir("openforge"))


def _read_toml(path: Path) -> dict[str, Any]:
    """Read a TOML file and return its contents, or an empty dict on failure."""
    if not path.is_file():
        return {}
    with open(path, "rb") as f:
        return cast(dict[str, Any], tomllib.load(f))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]


def _get_nested(data: dict[str, Any], dotted_key: str) -> str | None:
    """Retrieve a value from a nested dict using a dotted key like 'forge.url'."""
    keys = dotted_key.split(".")
    current: object = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if isinstance(current, bool):
        return "true" if current else "false"
    return str(current)  # pyright: ignore[reportUnknownArgumentType]


def _set_nested(data: dict[str, Any], dotted_key: str, value: object) -> None:
    """Set a value in a nested dict using a dotted key."""
    keys = dotted_key.split(".")
    current = data
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
    current[keys[-1]] = value


def _env_key_for(dotted_key: str) -> str | None:
    """Return the environment variable name for a config key, or None."""
    mapping: dict[str, str] = {
        "forge.url": "OPENFORGE_FORGE_URL",
    }
    return mapping.get(dotted_key)


def _is_ci() -> bool:
    """Detect whether we are running inside a CI environment."""
    return any(os.environ.get(var) for var in _CI_ENV_VARS)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(
    *,
    project_dir: Path | None = None,
    user_config_dir: Path | None = None,
) -> Config:
    """Load configuration with 4-level precedence: env > project > user > defaults."""

    user_dir = user_config_dir or _default_user_config_dir()
    proj_dir = project_dir or Path.cwd()

    user_data = _read_toml(user_dir / "config.toml")
    project_data = _read_toml(proj_dir / ".openforge.toml")

    # --- forge_url ---
    forge_url = Config.forge_url  # default
    user_val = _get_nested(user_data, "forge.url")
    if user_val is not None:
        forge_url = user_val
    proj_val = _get_nested(project_data, "forge.url")
    if proj_val is not None:
        forge_url = proj_val
    env_val = os.environ.get("OPENFORGE_FORGE_URL")
    if env_val is not None:
        forge_url = env_val

    # --- telemetry_enabled ---
    telemetry_enabled = Config.telemetry_enabled  # default
    user_tel = _get_nested(user_data, "telemetry.enabled")
    if user_tel is not None:
        telemetry_enabled = user_tel.lower() not in ("false", "0", "no")
    proj_tel = _get_nested(project_data, "telemetry.enabled")
    if proj_tel is not None:
        telemetry_enabled = proj_tel.lower() not in ("false", "0", "no")
    # DO_NOT_TRACK=1 disables telemetry
    if os.environ.get("DO_NOT_TRACK") == "1":
        telemetry_enabled = False
    # CI detection disables telemetry
    if _is_ci():
        telemetry_enabled = False

    return Config(forge_url=forge_url, telemetry_enabled=telemetry_enabled)


def get_config_value(
    key: str,
    *,
    project_dir: Path | None = None,
    user_config_dir: Path | None = None,
) -> ConfigValue:
    """Return a single config value along with which precedence layer it came from."""

    user_dir = user_config_dir or _default_user_config_dir()
    proj_dir = project_dir or Path.cwd()

    user_data = _read_toml(user_dir / "config.toml")
    project_data = _read_toml(proj_dir / ".openforge.toml")

    # Start with default
    value = _DEFAULTS.get(key)
    source = "default"

    # User layer
    user_val = _get_nested(user_data, key)
    if user_val is not None:
        value = user_val
        source = "user"

    # Project layer
    proj_val = _get_nested(project_data, key)
    if proj_val is not None:
        value = proj_val
        source = "project"

    # Env layer
    env_name = _env_key_for(key)
    if env_name is not None:
        env_val = os.environ.get(env_name)
        if env_val is not None:
            value = env_val
            source = "env"

    # Special: telemetry.enabled and DO_NOT_TRACK / CI
    if key == "telemetry.enabled":
        if os.environ.get("DO_NOT_TRACK") == "1" or _is_ci():
            value = "false"
            source = "env"

    if value is None:
        value = ""

    return ConfigValue(value=value, source=source)


def set_config_value(
    key: str,
    value: str,
    *,
    user_config_dir: Path | None = None,
) -> None:
    """Write a config value to the user-level config TOML file."""

    if key not in _DEFAULTS:
        msg = f"Unknown config key: {key!r}. Valid keys: {', '.join(sorted(_DEFAULTS))}"
        raise ValueError(msg)

    user_dir = user_config_dir or _default_user_config_dir()
    config_path = user_dir / "config.toml"

    # Read existing data
    data = _read_toml(config_path)

    # Coerce string values to proper types for known keys
    typed_value: object
    if key == "telemetry.enabled":
        if value.lower() in ("true", "1", "yes"):
            typed_value = True
        elif value.lower() in ("false", "0", "no"):
            typed_value = False
        else:
            typed_value = value
    else:
        typed_value = value

    # Set the value
    _set_nested(data, key, typed_value)

    # Ensure directory exists with restrictive permissions
    os.makedirs(user_dir, mode=0o700, exist_ok=True)

    # Write back with restrictive permissions
    import tomli_w

    with open(config_path, "wb") as f:
        tomli_w.dump(data, f)
    os.chmod(config_path, 0o600)
