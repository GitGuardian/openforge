# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

runner = CliRunner()


def _make_publish_app() -> typer.Typer:
    from openforge.publish import publish_command

    app = typer.Typer()
    app.command("publish")(publish_command)
    return app


def test_publish_requires_auth() -> None:
    """Publish fails with helpful message if not logged in."""
    app = _make_publish_app()

    with patch("openforge.publish.get_auth_token", return_value=None):
        result = runner.invoke(app, ["https://github.com/owner/repo"])
        assert result.exit_code == 1
        assert "Not logged in" in result.output
        assert "openforge auth login" in result.output


def test_publish_validates_git_url() -> None:
    """Publish rejects invalid URLs."""
    app = _make_publish_app()

    with patch("openforge.publish.get_auth_token", return_value="token"):
        result = runner.invoke(app, ["not-a-url"])
        assert result.exit_code == 1
        assert "Invalid" in result.output or "invalid" in result.output


def test_publish_sends_submission_to_forge() -> None:
    """Publish POSTs to /api/submissions and shows result."""
    app = _make_publish_app()

    mock_client = MagicMock()
    mock_client.submit.return_value = {
        "id": "sub-1",
        "status": "pending",
        "gitUrl": "https://github.com/owner/repo",
    }

    with (
        patch("openforge.publish.get_auth_token", return_value="token"),
        patch("openforge.publish.ForgeClient", return_value=mock_client),
    ):
        result = runner.invoke(app, ["https://github.com/owner/repo"])
        assert result.exit_code == 0, result.output
        assert "pending" in result.output.lower() or "Submission" in result.output
        mock_client.submit.assert_called_once_with("https://github.com/owner/repo", None)


def test_publish_with_description() -> None:
    """--description flag is sent to API."""
    app = _make_publish_app()

    mock_client = MagicMock()
    mock_client.submit.return_value = {
        "id": "sub-1",
        "status": "pending",
        "gitUrl": "https://github.com/owner/repo",
    }

    with (
        patch("openforge.publish.get_auth_token", return_value="token"),
        patch("openforge.publish.ForgeClient", return_value=mock_client),
    ):
        result = runner.invoke(
            app, ["https://github.com/owner/repo", "--description", "A great plugin"]
        )
        assert result.exit_code == 0, result.output
        mock_client.submit.assert_called_once_with(
            "https://github.com/owner/repo", "A great plugin"
        )


def test_publish_handles_server_error() -> None:
    """Graceful error handling on API failure."""
    from openforge.api_client import ForgeAPIError

    app = _make_publish_app()

    mock_client = MagicMock()
    mock_client.submit.side_effect = ForgeAPIError("Internal Server Error", status_code=500)

    with (
        patch("openforge.publish.get_auth_token", return_value="token"),
        patch("openforge.publish.ForgeClient", return_value=mock_client),
    ):
        result = runner.invoke(app, ["https://github.com/owner/repo"])
        assert result.exit_code == 1
        assert "Traceback" not in result.output
        assert "error" in result.output.lower() or "failed" in result.output.lower()


def test_publish_handles_network_error() -> None:
    """Graceful handling of connection refused."""
    import httpx

    app = _make_publish_app()

    mock_client = MagicMock()
    mock_client.submit.side_effect = httpx.ConnectError("Connection refused")

    with (
        patch("openforge.publish.get_auth_token", return_value="token"),
        patch("openforge.publish.ForgeClient", return_value=mock_client),
    ):
        result = runner.invoke(app, ["https://github.com/owner/repo"])
        assert result.exit_code == 1
        assert "Traceback" not in result.output


def test_publish_handles_duplicate_submission() -> None:
    """409 from server shows helpful message."""
    from openforge.api_client import ForgeAPIError

    app = _make_publish_app()

    mock_client = MagicMock()
    mock_client.submit.side_effect = ForgeAPIError(
        "This repository has already been submitted", status_code=409
    )

    with (
        patch("openforge.publish.get_auth_token", return_value="token"),
        patch("openforge.publish.ForgeClient", return_value=mock_client),
    ):
        result = runner.invoke(app, ["https://github.com/owner/repo"])
        assert result.exit_code == 1
        assert "already" in result.output.lower()


def test_publish_accepts_gitlab_url() -> None:
    """Publish accepts GitLab URLs."""
    app = _make_publish_app()

    mock_client = MagicMock()
    mock_client.submit.return_value = {"id": "sub-1", "status": "pending"}

    with (
        patch("openforge.publish.get_auth_token", return_value="token"),
        patch("openforge.publish.ForgeClient", return_value=mock_client),
    ):
        result = runner.invoke(app, ["https://gitlab.com/owner/repo"])
        assert result.exit_code == 0, result.output
        mock_client.submit.assert_called_once()
