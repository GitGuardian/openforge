# SPDX-License-Identifier: Apache-2.0
"""Integration tests for telemetry — verifies correct HTTP payload via respx."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import respx

from openforge.config_file import Config
from openforge.telemetry import send_install_event


def _capture_and_run(config: Config, **kwargs: object) -> httpx.Request:
    """Call send_install_event, capture the thread target, run it synchronously.

    Returns the captured httpx.Request for assertion.
    """
    captured_target = None

    def fake_thread(*, target: object, daemon: bool) -> MagicMock:
        nonlocal captured_target
        captured_target = target
        return MagicMock()

    with (
        patch("openforge.telemetry._get_config", return_value=config),
        patch("openforge.telemetry.threading.Thread", side_effect=fake_thread),
    ):
        send_install_event(**kwargs)  # type: ignore[arg-type]

    assert captured_target is not None

    # Now run the captured target with respx active
    captured_target()

    return respx.calls[0].request


@respx.mock
def test_send_install_event_posts_correct_payload() -> None:
    """send_install_event must POST the Forge-expected schema to /api/telemetry."""
    config = Config(forge_url="https://forge.test.local", telemetry_enabled=True)
    route = respx.post("https://forge.test.local/api/telemetry").mock(
        return_value=httpx.Response(204)
    )

    request = _capture_and_run(
        config,
        plugin_name="owner/repo",
        agents=["claude-code", "cursor"],
    )

    assert route.called
    body = json.loads(request.content)
    assert body["plugin_name"] == "owner/repo"
    assert body["source"] == "cli"
    assert body["agents"] == ["claude-code", "cursor"]
    assert "cli_version" in body
    assert isinstance(body.get("is_ci"), bool)
    # Must NOT contain legacy fields
    assert "event" not in body
    assert "content_type" not in body
    assert "skills" not in body


@respx.mock
def test_send_install_event_includes_skill_name() -> None:
    """send_install_event includes skill_name when provided."""
    config = Config(forge_url="https://forge.test.local", telemetry_enabled=True)
    route = respx.post("https://forge.test.local/api/telemetry").mock(
        return_value=httpx.Response(204)
    )

    request = _capture_and_run(
        config,
        plugin_name="owner/repo",
        agents=["claude-code"],
        skill_name="my-skill",
    )

    assert route.called
    body = json.loads(request.content)
    assert body["skill_name"] == "my-skill"


@respx.mock
def test_send_install_event_omits_skill_name_when_none() -> None:
    """send_install_event omits skill_name when not provided."""
    config = Config(forge_url="https://forge.test.local", telemetry_enabled=True)
    route = respx.post("https://forge.test.local/api/telemetry").mock(
        return_value=httpx.Response(204)
    )

    request = _capture_and_run(
        config,
        plugin_name="owner/repo",
        agents=[],
    )

    assert route.called
    body = json.loads(request.content)
    assert "skill_name" not in body
