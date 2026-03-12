# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from openforge.config_file import Config
from openforge.telemetry import send_install_event


def test_telemetry_skips_http_url(tmp_path: Path) -> None:
    """Telemetry must NOT send when the forge URL uses plain HTTP."""
    insecure_config = Config(forge_url="http://evil.example.com", telemetry_enabled=True)

    with (
        patch("openforge.telemetry._get_config", return_value=insecure_config),
        patch("openforge.telemetry.threading.Thread") as mock_thread,
        patch.dict("os.environ", {}, clear=False),
    ):
        os.environ.pop("OPENFORGE_TELEMETRY_FORCE", None)
        send_install_event(plugin_name="test", agents=[])
        mock_thread.assert_not_called()


def test_telemetry_force_allows_http(tmp_path: Path) -> None:
    """OPENFORGE_TELEMETRY_FORCE=1 allows telemetry over HTTP (for E2E testing)."""
    http_config = Config(forge_url="http://localhost:3000", telemetry_enabled=True)

    with (
        patch("openforge.telemetry._get_config", return_value=http_config),
        patch("openforge.telemetry.threading.Thread") as mock_thread,
        patch.dict("os.environ", {"OPENFORGE_TELEMETRY_FORCE": "1"}),
    ):
        send_install_event(plugin_name="test", agents=[])
        mock_thread.assert_called_once()


def test_telemetry_force_uses_non_daemon_thread_and_joins(tmp_path: Path) -> None:
    """OPENFORGE_TELEMETRY_FORCE makes the thread non-daemon and joins it."""
    config = Config(forge_url="http://localhost:3000", telemetry_enabled=True)

    with (
        patch("openforge.telemetry._get_config", return_value=config),
        patch("openforge.telemetry.threading.Thread") as mock_thread_cls,
        patch.dict("os.environ", {"OPENFORGE_TELEMETRY_FORCE": "1"}),
    ):
        mock_instance = MagicMock()
        mock_thread_cls.return_value = mock_instance

        send_install_event(plugin_name="test", agents=[])

        # Thread created with daemon=False
        mock_thread_cls.assert_called_once()
        _, kwargs = mock_thread_cls.call_args
        assert kwargs["daemon"] is False

        # Thread.join called with timeout
        mock_instance.start.assert_called_once()
        mock_instance.join.assert_called_once_with(timeout=5)


def test_telemetry_sends_with_https_url(tmp_path: Path) -> None:
    """Telemetry SHOULD send when the forge URL uses HTTPS."""
    secure_config = Config(forge_url="https://forge.example.com", telemetry_enabled=True)

    with (
        patch("openforge.telemetry._get_config", return_value=secure_config),
        patch("openforge.telemetry.threading.Thread") as mock_thread,
    ):
        send_install_event(plugin_name="test", agents=[])
        mock_thread.assert_called_once()


def test_telemetry_noop_when_disabled() -> None:
    """send_install_event must be a no-op when telemetry_enabled is False."""
    config = Config(forge_url="https://forge.example.com", telemetry_enabled=False)

    with (
        patch("openforge.telemetry._get_config", return_value=config),
        patch("openforge.telemetry.threading.Thread") as mock_thread,
    ):
        send_install_event(plugin_name="test-plugin", agents=[])
        mock_thread.assert_not_called()


def test_telemetry_thread_calls_httpx_post_with_correct_payload() -> None:
    """The background thread should call httpx.post with the Forge-expected schema."""
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
        patch("openforge.telemetry._is_ci", return_value=False),
    ):
        send_install_event(
            plugin_name="owner/repo",
            agents=["claude-code", "cursor"],
        )

    assert captured_target is not None

    with patch("httpx.post") as mock_post:
        captured_target()
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs["json"]

        # Required Forge fields
        assert payload["plugin_name"] == "owner/repo"
        assert payload["source"] == "cli"
        assert payload["agents"] == ["claude-code", "cursor"]
        assert "cli_version" in payload
        assert payload["is_ci"] is False

        # Must NOT contain legacy fields
        assert "event" not in payload
        assert "content_type" not in payload
        assert "skills" not in payload


def test_telemetry_includes_skill_name_when_provided() -> None:
    """send_install_event includes skill_name in payload when given."""
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
        send_install_event(
            plugin_name="owner/repo",
            agents=["claude-code"],
            skill_name="my-skill",
        )

    assert captured_target is not None

    with patch("httpx.post") as mock_post:
        captured_target()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["skill_name"] == "my-skill"


def test_telemetry_omits_skill_name_when_none() -> None:
    """send_install_event omits skill_name when not provided."""
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
        send_install_event(plugin_name="owner/repo", agents=[])

    assert captured_target is not None

    with patch("httpx.post") as mock_post:
        captured_target()
        payload = mock_post.call_args.kwargs["json"]
        assert "skill_name" not in payload


def test_telemetry_is_ci_true_when_in_ci() -> None:
    """send_install_event sets is_ci=True when running in CI."""
    config = Config(forge_url="https://forge.example.com", telemetry_enabled=True)

    captured_target = None

    def fake_thread(*, target: object, daemon: bool) -> MagicMock:
        nonlocal captured_target
        captured_target = target
        return MagicMock()

    with (
        patch("openforge.telemetry._get_config", return_value=config),
        patch("openforge.telemetry.threading.Thread", side_effect=fake_thread),
        patch("openforge.telemetry._is_ci", return_value=True),
    ):
        send_install_event(plugin_name="test", agents=[])

    assert captured_target is not None

    with patch("httpx.post") as mock_post:
        captured_target()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["is_ci"] is True


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
        send_install_event(plugin_name="test", agents=[])

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
