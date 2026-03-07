# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import threading

from openforge.config_file import Config, load_config

_cached_config: Config | None = None


def _get_config() -> Config:
    global _cached_config  # noqa: PLW0603
    if _cached_config is None:
        _cached_config = load_config()
    return _cached_config


def send_event(event: str, data: dict[str, object]) -> None:
    """Fire-and-forget telemetry event. Never raises, never blocks."""
    config: Config = _get_config()
    if not config.telemetry_enabled:
        return

    if not config.forge_url.startswith("https://"):
        return

    payload: dict[str, object] = {"event": event, **data}

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

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
