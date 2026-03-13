# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import typer
from typer.testing import CliRunner

runner = CliRunner()


def _make_auth_app() -> typer.Typer:
    from openforge.auth import auth_app

    app = typer.Typer()
    app.add_typer(auth_app, name="auth")
    return app


def test_login_prompts_for_email_and_password(tmp_path: Path) -> None:
    """Login command prompts for email and password, then stores token."""
    app = _make_auth_app()

    mock_response = MagicMock()
    mock_response.session = MagicMock()
    mock_response.session.access_token = "test-access-token"
    mock_response.session.refresh_token = "test-refresh-token"
    mock_response.user = MagicMock()
    mock_response.user.email = "test@example.com"
    mock_response.user.id = "user-123"

    token_dir = tmp_path / "config"

    with (
        patch("openforge.auth._get_token_dir", return_value=token_dir),
        patch("openforge.auth._sign_in_with_password", return_value=mock_response),
    ):
        result = runner.invoke(app, ["auth", "login"], input="test@example.com\npassword123\n")
        assert result.exit_code == 0, result.output
        assert "Logged in" in result.output

        # Verify token file was written
        token_file = token_dir / "token.json"
        assert token_file.exists()
        token_data = json.loads(token_file.read_text())
        assert token_data["access_token"] == "test-access-token"
        assert token_data["refresh_token"] == "test-refresh-token"
        assert token_data["email"] == "test@example.com"


def test_login_handles_auth_failure(tmp_path: Path) -> None:
    """Login shows error on authentication failure."""
    app = _make_auth_app()

    token_dir = tmp_path / "config"

    with (
        patch("openforge.auth._get_token_dir", return_value=token_dir),
        patch(
            "openforge.auth._sign_in_with_password",
            side_effect=ValueError("Invalid login credentials"),
        ),
    ):
        result = runner.invoke(app, ["auth", "login"], input="bad@example.com\nwrong\n")
        assert result.exit_code == 1
        assert "Invalid login credentials" in result.output


def test_logout_clears_token(tmp_path: Path) -> None:
    """Logout removes stored token file."""
    app = _make_auth_app()

    token_dir = tmp_path / "config"
    token_dir.mkdir(parents=True)
    token_file = token_dir / "token.json"
    token_file.write_text(json.dumps({"access_token": "old-token"}))

    with patch("openforge.auth._get_token_dir", return_value=token_dir):
        result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0, result.output
        assert "Logged out" in result.output
        assert not token_file.exists()


def test_logout_when_not_logged_in(tmp_path: Path) -> None:
    """Logout when no token file shows appropriate message."""
    app = _make_auth_app()

    token_dir = tmp_path / "config"

    with patch("openforge.auth._get_token_dir", return_value=token_dir):
        result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code == 0, result.output
        assert "Not logged in" in result.output or "Logged out" in result.output


def test_status_shows_authenticated_user(tmp_path: Path) -> None:
    """Status shows email when logged in."""
    app = _make_auth_app()

    token_dir = tmp_path / "config"
    token_dir.mkdir(parents=True)
    (token_dir / "token.json").write_text(
        json.dumps(
            {
                "access_token": "test-token",
                "refresh_token": "test-refresh",
                "email": "test@example.com",
                "user_id": "user-123",
            }
        )
    )

    with patch("openforge.auth._get_token_dir", return_value=token_dir):
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0, result.output
        assert "test@example.com" in result.output


def test_status_shows_not_authenticated(tmp_path: Path) -> None:
    """Status shows not logged in when no token."""
    app = _make_auth_app()

    token_dir = tmp_path / "config"

    with patch("openforge.auth._get_token_dir", return_value=token_dir):
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code == 0, result.output
        assert "Not logged in" in result.output


def test_get_auth_token_returns_token(tmp_path: Path) -> None:
    """get_auth_token returns stored access token."""
    from openforge.auth import get_auth_token

    token_dir = tmp_path / "config"
    token_dir.mkdir(parents=True)
    (token_dir / "token.json").write_text(
        json.dumps({"access_token": "my-token", "refresh_token": "refresh", "email": "a@b.com"})
    )

    with patch("openforge.auth._get_token_dir", return_value=token_dir):
        token = get_auth_token()
        assert token == "my-token"


def test_get_auth_token_returns_none_when_no_file(tmp_path: Path) -> None:
    """get_auth_token returns None when no token file."""
    from openforge.auth import get_auth_token

    token_dir = tmp_path / "config"

    with patch("openforge.auth._get_token_dir", return_value=token_dir):
        token = get_auth_token()
        assert token is None


def test_read_token_returns_none_on_corrupt_json(tmp_path: Path) -> None:
    """_read_token returns None when token file contains invalid JSON."""
    from openforge.auth import _read_token

    token_dir = tmp_path / "config"
    token_dir.mkdir(parents=True)
    (token_dir / "token.json").write_text("not valid json{{{")

    with patch("openforge.auth._get_token_dir", return_value=token_dir):
        result = _read_token()
        assert result is None


def test_save_token_atomic_write(tmp_path: Path) -> None:
    """Token file should be written atomically via tmp+rename, never world-readable."""
    import os

    from openforge.auth import _store_token

    token_dir = tmp_path / "config"
    token_dir.mkdir()

    with patch("openforge.auth._get_token_dir", return_value=token_dir):
        _store_token(
            access_token="at",
            refresh_token="rt",
            email="a@b.com",
            user_id="u1",
        )

    token_file = token_dir / "token.json"
    # File should exist with correct permissions
    assert token_file.exists()
    mode = os.stat(token_file).st_mode & 0o777
    assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
    # No leftover .tmp file
    assert not (token_dir / "token.json.tmp").exists()
    # Verify content
    data = json.loads(token_file.read_text())
    assert data["access_token"] == "at"


def test_read_token_warns_on_corrupt_json(tmp_path: Path, capsys: object) -> None:
    """Corrupt token.json should print warning to stderr, not silently return None."""

    from openforge.auth import _read_token

    token_dir = tmp_path / "config"
    token_dir.mkdir(parents=True)
    (token_dir / "token.json").write_text("{invalid json", encoding="utf-8")

    with patch("openforge.auth._get_token_dir", return_value=token_dir):
        result = _read_token()

    assert result is None
    captured = capsys.readouterr()  # type: ignore[union-attr]
    assert "invalid JSON" in captured.err


def test_read_token_warns_on_os_error(tmp_path: Path, capsys: object) -> None:
    """_read_token should warn on OSError, not silently return None."""
    from openforge.auth import _read_token

    token_dir = tmp_path / "config"
    token_dir.mkdir(parents=True)
    token_file = token_dir / "token.json"
    token_file.write_text('{"access_token": "x"}', encoding="utf-8")

    with (
        patch("openforge.auth._get_token_dir", return_value=token_dir),
        patch("openforge.auth.Path.read_text", side_effect=OSError("permission denied")),
    ):
        result = _read_token()

    assert result is None
    captured = capsys.readouterr()  # type: ignore[union-attr]
    assert "Could not read" in captured.err


def test_read_token_returns_none_when_missing_access_token(tmp_path: Path) -> None:
    """_read_token returns None when token file has no access_token key."""
    from openforge.auth import _read_token

    token_dir = tmp_path / "config"
    token_dir.mkdir(parents=True)
    (token_dir / "token.json").write_text(json.dumps({"some_key": "value"}))

    with patch("openforge.auth._get_token_dir", return_value=token_dir):
        result = _read_token()
        assert result is None


def test_sign_in_with_password_success() -> None:
    """_sign_in_with_password returns namespace on successful auth."""
    from openforge.auth import _sign_in_with_password

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "at-123",
        "refresh_token": "rt-456",
        "user": {"email": "user@example.com", "id": "uid-789"},
    }

    with patch("httpx.post", return_value=mock_response):
        result = _sign_in_with_password("user@example.com", "pass", "https://forge.example.com")
        assert result.session.access_token == "at-123"
        assert result.session.refresh_token == "rt-456"
        assert result.user.email == "user@example.com"
        assert result.user.id == "uid-789"


def test_sign_in_with_password_failure() -> None:
    """_sign_in_with_password raises ValueError on auth failure."""
    import pytest

    from openforge.auth import _sign_in_with_password

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.json.return_value = {"error_description": "Invalid credentials"}

    with (
        patch("httpx.post", return_value=mock_response),
        pytest.raises(ValueError, match="Invalid credentials"),
    ):
        _sign_in_with_password("bad@example.com", "wrong", "https://forge.example.com")


def test_sign_in_with_password_failure_fallback_msg() -> None:
    """_sign_in_with_password uses fallback message when no error_description."""
    import pytest

    from openforge.auth import _sign_in_with_password

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {}

    with (
        patch("httpx.post", return_value=mock_response),
        pytest.raises(ValueError, match="Authentication failed"),
    ):
        _sign_in_with_password("a@b.com", "x", "https://forge.example.com")


def test_login_uses_supabase_url_not_forge_url(tmp_path: Path) -> None:
    """Login command uses config.supabase_url for GoTrue auth, not forge_url."""
    app = _make_auth_app()

    mock_response = MagicMock()
    mock_response.session = MagicMock()
    mock_response.session.access_token = "token"
    mock_response.session.refresh_token = "refresh"
    mock_response.user = MagicMock()
    mock_response.user.email = "a@b.com"
    mock_response.user.id = "u1"

    token_dir = tmp_path / "config"

    with (
        patch("openforge.auth._get_token_dir", return_value=token_dir),
        patch("openforge.auth._sign_in_with_password", return_value=mock_response) as mock_sign_in,
        patch(
            "openforge.config_file.load_config",
            return_value=MagicMock(
                forge_url="https://forge.example.com",
                supabase_url="http://localhost:54321",
            ),
        ),
    ):
        result = runner.invoke(app, ["auth", "login"], input="a@b.com\npass\n")
        assert result.exit_code == 0, result.output
        # Must pass supabase_url, NOT forge_url
        mock_sign_in.assert_called_once_with("a@b.com", "pass", "http://localhost:54321")


def test_login_handles_network_error(tmp_path: Path) -> None:
    """Network error during login should show friendly message, not traceback."""
    import httpx

    app = _make_auth_app()
    token_dir = tmp_path / "config"

    with (
        patch("openforge.auth._get_token_dir", return_value=token_dir),
        patch(
            "openforge.auth._sign_in_with_password",
            side_effect=httpx.ConnectError("Connection refused"),
        ),
    ):
        result = runner.invoke(app, ["auth", "login"], input="a@b.com\npass\n")
        assert result.exit_code == 1
        assert "Traceback" not in result.output
        assert "connect" in result.output.lower() or "network" in result.output.lower()


def test_token_file_has_restrictive_permissions(tmp_path: Path) -> None:
    """Token file is written with 600 permissions."""
    import os

    app = _make_auth_app()

    mock_response = MagicMock()
    mock_response.session = MagicMock()
    mock_response.session.access_token = "token"
    mock_response.session.refresh_token = "refresh"
    mock_response.user = MagicMock()
    mock_response.user.email = "a@b.com"
    mock_response.user.id = "u1"

    token_dir = tmp_path / "config"

    with (
        patch("openforge.auth._get_token_dir", return_value=token_dir),
        patch("openforge.auth._sign_in_with_password", return_value=mock_response),
    ):
        result = runner.invoke(app, ["auth", "login"], input="a@b.com\npass\n")
        assert result.exit_code == 0, result.output

        token_file = token_dir / "token.json"
        mode = os.stat(token_file).st_mode & 0o777
        assert mode == 0o600, f"Expected 0o600, got {oct(mode)}"
