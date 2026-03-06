from __future__ import annotations

import threading

import httpx

from openforge.config_file import Config, load_config


def send_event(event: str, data: dict[str, object]) -> None:
    """Fire-and-forget telemetry event. Never raises, never blocks."""
    config: Config = load_config()
    if not config.telemetry_enabled:
        return

    if not config.forge_url.startswith("https://"):
        return

    payload: dict[str, object] = {"event": event, **data}

    def _send() -> None:
        try:
            httpx.post(
                f"{config.forge_url}/api/telemetry",
                json=payload,
                timeout=5.0,
            )
        except Exception:  # noqa: BLE001
            # Fire-and-forget: silently ignore all telemetry errors.
            # This includes network, TLS, timeout, and config errors.
            # Telemetry must never block or crash the CLI.
            pass

    thread = threading.Thread(target=_send, daemon=True)
    thread.start()
