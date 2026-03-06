from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from openforge.config_file import Config
from openforge.telemetry import send_event


def test_telemetry_skips_http_url(tmp_path: Path) -> None:
    """Telemetry must NOT send when the forge URL uses plain HTTP."""
    insecure_config = Config(forge_url="http://evil.example.com", telemetry_enabled=True)

    with (
        patch("openforge.telemetry.load_config", return_value=insecure_config),
        patch("openforge.telemetry.threading.Thread") as mock_thread,
    ):
        send_event("test", {"key": "value"})
        mock_thread.assert_not_called()


def test_telemetry_sends_with_https_url(tmp_path: Path) -> None:
    """Telemetry SHOULD send when the forge URL uses HTTPS."""
    secure_config = Config(forge_url="https://forge.example.com", telemetry_enabled=True)

    with (
        patch("openforge.telemetry.load_config", return_value=secure_config),
        patch("openforge.telemetry.threading.Thread") as mock_thread,
    ):
        send_event("test", {"key": "value"})
        mock_thread.assert_called_once()


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
