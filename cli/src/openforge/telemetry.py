# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
import threading

from openforge.config_file import Config, load_config

_cached_config: Config | None = None

# CI environment variables (same list as config_file.py)
_CI_ENV_VARS: tuple[str, ...] = (
    "CI",
    "GITHUB_ACTIONS",
    "GITLAB_CI",
    "JENKINS_URL",
    "CIRCLECI",
    "TRAVIS",
    "BUILDKITE",
)


def _get_config() -> Config:
    global _cached_config  # noqa: PLW0603
    if _cached_config is None:
        _cached_config = load_config()
    return _cached_config


def _is_ci() -> bool:
    """Detect whether we are running inside a CI environment."""
    return any(os.environ.get(var) for var in _CI_ENV_VARS)


def send_install_event(
    *,
    plugin_name: str,
    agents: list[str],
    skill_name: str | None = None,
) -> None:
    """Fire-and-forget install telemetry event. Never raises, never blocks.

    Sends a payload matching the Forge's POST /api/telemetry schema:
      plugin_name (required), source="cli", agents, cli_version, is_ci,
      skill_name (optional).
    """
    config: Config = _get_config()
    if not config.telemetry_enabled:
        return

    force = bool(os.environ.get("OPENFORGE_TELEMETRY_FORCE"))
    if not config.forge_url.startswith("https://") and not force:
        return

    from openforge import __version__

    payload: dict[str, object] = {
        "plugin_name": plugin_name,
        "source": "cli",
        "agents": agents,
        "cli_version": __version__,
        "is_ci": _is_ci(),
    }
    if skill_name is not None:
        payload["skill_name"] = skill_name

    def _send() -> None:
        try:
            import httpx

            httpx.post(
                f"{config.forge_url}/api/telemetry",
                json=payload,
                timeout=5.0,
            )
        except Exception:  # noqa: BLE001  # nosec B110
            # Fire-and-forget: silently ignore all telemetry errors.
            # This includes network, TLS, timeout, and config errors.
            # Telemetry must never block or crash the CLI.
            pass

    thread = threading.Thread(target=_send, daemon=not force)
    thread.start()
    if force:
        thread.join(timeout=5)
