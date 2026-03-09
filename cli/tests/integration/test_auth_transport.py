# SPDX-License-Identifier: Apache-2.0
# pyright: reportPrivateUsage=false
"""Integration tests for auth module — HTTP transport layer via respx.

These tests verify:
- Correct GoTrue endpoint URL construction
- Correct request headers and body format
- Correct response parsing into SimpleNamespace
- Error handling for auth failure responses
"""

from __future__ import annotations

import json
from typing import cast

import httpx
import pytest
import respx
from httpx import Response

from openforge.auth import _sign_in_with_password


def _get_request(route: respx.Route, index: int = 0) -> httpx.Request:
    """Extract a typed httpx.Request from a respx route's call history."""
    request = cast(httpx.Request, route.calls[index].request)  # type: ignore[index]
    return request


class TestSignInTransport:
    """Test _sign_in_with_password() at the HTTP transport layer."""

    @respx.mock
    def test_sends_post_to_gotrue_token_endpoint(self, mock_supabase_url: str) -> None:
        """Verify request goes to /auth/v1/token?grant_type=password."""
        route = respx.post(f"{mock_supabase_url}/auth/v1/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "at-123",
                    "refresh_token": "rt-456",
                    "user": {"email": "test@example.com", "id": "user-1"},
                },
            )
        )

        _sign_in_with_password("test@example.com", "password123", mock_supabase_url)

        assert route.called
        request = _get_request(route)
        assert "grant_type=password" in str(request.url)

    @respx.mock
    def test_sends_email_and_password_in_body(self, mock_supabase_url: str) -> None:
        """Verify request body contains email and password as JSON."""
        route = respx.post(f"{mock_supabase_url}/auth/v1/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "at-123",
                    "refresh_token": "rt-456",
                    "user": {"email": "test@example.com", "id": "user-1"},
                },
            )
        )

        _sign_in_with_password("test@example.com", "password123", mock_supabase_url)

        request = _get_request(route)
        body = json.loads(request.content)
        assert body["email"] == "test@example.com"
        assert body["password"] == "password123"

    @respx.mock
    def test_sends_content_type_json(self, mock_supabase_url: str) -> None:
        """Verify Content-Type header is application/json."""
        route = respx.post(f"{mock_supabase_url}/auth/v1/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "at-123",
                    "refresh_token": "rt-456",
                    "user": {"email": "test@example.com", "id": "user-1"},
                },
            )
        )

        _sign_in_with_password("test@example.com", "password", mock_supabase_url)

        request = _get_request(route)
        assert "application/json" in request.headers["content-type"]

    @respx.mock
    def test_returns_access_token(self, mock_supabase_url: str) -> None:
        """Verify successful auth returns access_token."""
        respx.post(f"{mock_supabase_url}/auth/v1/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "eyJ-access-token",
                    "refresh_token": "eyJ-refresh-token",
                    "user": {"email": "user@example.com", "id": "uid-789"},
                },
            )
        )

        result = _sign_in_with_password("user@example.com", "pass", mock_supabase_url)
        assert result.session.access_token == "eyJ-access-token"

    @respx.mock
    def test_returns_refresh_token(self, mock_supabase_url: str) -> None:
        """Verify successful auth returns refresh_token."""
        respx.post(f"{mock_supabase_url}/auth/v1/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "at",
                    "refresh_token": "eyJ-refresh-token",
                    "user": {"email": "user@example.com", "id": "uid"},
                },
            )
        )

        result = _sign_in_with_password("user@example.com", "pass", mock_supabase_url)
        assert result.session.refresh_token == "eyJ-refresh-token"

    @respx.mock
    def test_returns_user_email(self, mock_supabase_url: str) -> None:
        """Verify successful auth returns user email."""
        respx.post(f"{mock_supabase_url}/auth/v1/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "at",
                    "refresh_token": "rt",
                    "user": {"email": "alice@example.com", "id": "uid-1"},
                },
            )
        )

        result = _sign_in_with_password("alice@example.com", "pass", mock_supabase_url)
        assert result.user.email == "alice@example.com"

    @respx.mock
    def test_returns_user_id(self, mock_supabase_url: str) -> None:
        """Verify successful auth returns user id."""
        respx.post(f"{mock_supabase_url}/auth/v1/token").mock(
            return_value=Response(
                200,
                json={
                    "access_token": "at",
                    "refresh_token": "rt",
                    "user": {"email": "a@b.com", "id": "uid-42"},
                },
            )
        )

        result = _sign_in_with_password("a@b.com", "pass", mock_supabase_url)
        assert result.user.id == "uid-42"

    @respx.mock
    def test_raises_on_invalid_credentials(self, mock_supabase_url: str) -> None:
        """Verify ValueError raised on 400 with error_description."""
        respx.post(f"{mock_supabase_url}/auth/v1/token").mock(
            return_value=Response(
                400,
                json={
                    "error": "invalid_grant",
                    "error_description": "Invalid login credentials",
                },
            )
        )

        with pytest.raises(ValueError, match="Invalid login credentials"):
            _sign_in_with_password("bad@example.com", "wrong", mock_supabase_url)

    @respx.mock
    def test_raises_on_server_error_with_msg(self, mock_supabase_url: str) -> None:
        """Verify ValueError raised on 500 with msg field."""
        respx.post(f"{mock_supabase_url}/auth/v1/token").mock(
            return_value=Response(500, json={"msg": "Internal error"})
        )

        with pytest.raises(ValueError, match="Internal error"):
            _sign_in_with_password("test@example.com", "password", mock_supabase_url)

    @respx.mock
    def test_raises_with_fallback_message(self, mock_supabase_url: str) -> None:
        """Verify ValueError raised with fallback when no error_description or msg."""
        respx.post(f"{mock_supabase_url}/auth/v1/token").mock(return_value=Response(401, json={}))

        with pytest.raises(ValueError, match="Authentication failed"):
            _sign_in_with_password("a@b.com", "x", mock_supabase_url)
