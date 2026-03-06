# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from openforge.config_file import Config
from openforge.telemetry import send_event


def test_telemetry_skips_http_url(tmp_path: Path) -> None:
    """Telemetry must NOT send when the forge URL uses plain HTTP."""
    insecure_config = Config(forge_url="http://evil.example.com", telemetry_enabled=True)

    with (
        patch("openforge.telemetry._get_config", return_value=insecure_config),
        patch("openforge.telemetry.threading.Thread") as mock_thread,
    ):
        send_event("test", {"key": "value"})
        mock_thread.assert_not_called()


def test_telemetry_sends_with_https_url(tmp_path: Path) -> None:
    """Telemetry SHOULD send when the forge URL uses HTTPS."""
    secure_config = Config(forge_url="https://forge.example.com", telemetry_enabled=True)

    with (
        patch("openforge.telemetry._get_config", return_value=secure_config),
        patch("openforge.telemetry.threading.Thread") as mock_thread,
    ):
        send_event("test", {"key": "value"})
        mock_thread.assert_called_once()


def test_telemetry_noop_when_disabled() -> None:
    """send_event must be a no-op when telemetry_enabled is False."""
    config = Config(forge_url="https://forge.example.com", telemetry_enabled=False)

    with (
        patch("openforge.telemetry._get_config", return_value=config),
        patch("openforge.telemetry.threading.Thread") as mock_thread,
    ):
        send_event("install", {"name": "test-plugin"})
        mock_thread.assert_not_called()


def test_telemetry_thread_calls_httpx_post() -> None:
    """The background thread should call httpx.post with the correct payload."""
    config = Config(forge_url="https://forge.example.com", telemetry_enabled=True)

    captured_target = None

    def fake_thread(*, target: object, daemon: bool) -> MagicMock:
        nonlocal captured_target
        captured_target = target
        mock = MagicMock()
        return mock

    with (
        patch("openforge.telemetry._get_config", return_value=config),
        patch("openforge.telemetry.threading.Thread", side_effect=fake_thread),
    ):
        send_event("install", {"name": "my-plugin"})

    # Verify the target function was captured
    assert captured_target is not None

    # Call the target function and verify httpx.post is called
    with patch("httpx.post") as mock_post:
        captured_target()
        mock_post.assert_called_once_with(
            "https://forge.example.com/api/telemetry",
            json={"event": "install", "name": "my-plugin"},
            timeout=5.0,
        )


def test_telemetry_thread_silently_ignores_errors() -> None:
    """The _send function must silently catch all exceptions."""
    config = Config(forge_url="https://forge.example.com", telemetry_enabled=True)

    captured_target = None

    def fake_thread(*, target: object, daemon: bool) -> MagicMock:
        nonlocal captured_target
        captured_target = target
        return MagicMock()

    with (
        patch("openforge.telemetry._get_config", return_value=config),
        patch("openforge.telemetry.threading.Thread", side_effect=fake_thread),
    ):
        send_event("test", {"key": "value"})

    assert captured_target is not None

    # Simulate httpx.post raising an error -- should not propagate
    with patch("httpx.post", side_effect=ConnectionError("network down")):
        captured_target()  # must not raise


def test_telemetry_get_config_caches() -> None:
    """_get_config caches its result in the module-level _cached_config."""
    import openforge.telemetry as tel_mod

    original = tel_mod._cached_config
    try:
        tel_mod._cached_config = None
        with patch("openforge.telemetry.load_config") as mock_load:
            mock_load.return_value = Config()
            result1 = tel_mod._get_config()
            result2 = tel_mod._get_config()
            # load_config should only be called once (caching)
            mock_load.assert_called_once()
            assert result1 is result2
    finally:
        tel_mod._cached_config = original


def test_find_telemetry_excludes_query(tmp_path: Path) -> None:
    """The find command must NOT send the raw search query in telemetry."""
    from openforge.lock import write_lock
    from openforge.types import LockFile

    lock_path = tmp_path / ".openforge-lock.json"
    write_lock(lock_path, LockFile(entries={}))

    captured_payloads: list[dict[str, object]] = []

    def fake_send_event(event: str, data: dict[str, object]) -> None:
        captured_payloads.append({"event": event, **data})

    with (
        patch("openforge.find_cmd.get_project_dir", return_value=tmp_path),
        patch("openforge.find_cmd.send_event", side_effect=fake_send_event),
    ):
        import typer
        from typer.testing import CliRunner

        from openforge.find_cmd import find_command

        test_app = typer.Typer()
        test_app.command("find")(find_command)

        @test_app.command("noop")
        def _noop() -> None:
            """Placeholder."""

        _ = _noop

        runner = CliRunner()
        runner.invoke(test_app, ["find", "secret-search-term"])

    assert len(captured_payloads) == 1
    payload = captured_payloads[0]
    assert "query" not in payload
    assert "secret-search-term" not in str(payload)
    assert "results_count" in payload
