# SPDX-License-Identifier: Apache-2.0
"""Integration tests for ForgeClient — tests at the HTTP transport layer using respx.

These tests verify:
- Correct URL construction
- Correct headers (Authorization, Content-Type)
- Correct request body format
- Correct response parsing
- Error handling for non-200 responses

Unlike unit tests that mock `client._post()`, these tests let the real
httpx calls flow through to respx, which intercepts at the transport layer.
"""

from __future__ import annotations

import json
from typing import cast

import httpx
import pytest
import respx
from httpx import Response

from openforge.api_client import ForgeAPIError, ForgeClient


def _get_request(route: respx.Route, index: int = 0) -> httpx.Request:
    """Extract a typed httpx.Request from a respx route's call history."""
    request = cast(httpx.Request, route.calls[index].request)  # type: ignore[index]
    return request


class TestForgeClientSubmit:
    """Test ForgeClient.submit() at the HTTP transport layer."""

    @respx.mock
    def test_submit_sends_correct_url_and_method(self, mock_forge_url: str) -> None:
        """Verify submit() POSTs to /api/submissions."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-1", "status": "pending"})
        )

        client = ForgeClient(token="test-token-123", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo")

        assert route.called
        assert route.call_count == 1

    @respx.mock
    def test_submit_sends_auth_header(self, mock_forge_url: str) -> None:
        """Verify submit() includes Bearer token in Authorization header."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-1", "status": "pending"})
        )

        client = ForgeClient(token="my-secret-token", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo")

        request = _get_request(route)
        assert request.headers["authorization"] == "Bearer my-secret-token"

    @respx.mock
    def test_submit_sends_content_type_json(self, mock_forge_url: str) -> None:
        """Verify submit() sends Content-Type: application/json."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-1", "status": "pending"})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo")

        request = _get_request(route)
        assert "application/json" in request.headers["content-type"]

    @respx.mock
    def test_submit_sends_git_url_in_body(self, mock_forge_url: str) -> None:
        """Verify submit() sends gitUrl in request body."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-1", "status": "pending"})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo")

        request = _get_request(route)
        body = json.loads(request.content)
        assert body["gitUrl"] == "https://github.com/owner/repo"

    @respx.mock
    def test_submit_sends_description_in_body(self, mock_forge_url: str) -> None:
        """Verify submit() includes description when provided."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-1", "status": "pending"})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo", "A great plugin")

        body = json.loads(_get_request(route).content)
        assert body["description"] == "A great plugin"

    @respx.mock
    def test_submit_omits_description_when_none(self, mock_forge_url: str) -> None:
        """Verify submit() does not send description key when None."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-1", "status": "pending"})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo")

        body = json.loads(_get_request(route).content)
        assert "description" not in body

    @respx.mock
    def test_submit_parses_response_json(self, mock_forge_url: str) -> None:
        """Verify submit() returns parsed JSON response."""
        respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(
                201,
                json={
                    "id": "sub-42",
                    "status": "pending",
                    "gitUrl": "https://github.com/owner/repo",
                },
            )
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        result = client.submit("https://github.com/owner/repo")

        assert result["id"] == "sub-42"
        assert result["status"] == "pending"
        assert result["gitUrl"] == "https://github.com/owner/repo"

    @respx.mock
    def test_submit_raises_on_401(self, mock_forge_url: str) -> None:
        """Verify submit() raises ForgeAPIError on 401 Unauthorized."""
        respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(401, json={"error": "Unauthorized"})
        )

        client = ForgeClient(token="bad-token", forge_url=mock_forge_url)
        with pytest.raises(ForgeAPIError) as exc_info:
            client.submit("https://github.com/owner/repo")
        assert exc_info.value.status_code == 401

    @respx.mock
    def test_submit_raises_on_409_duplicate(self, mock_forge_url: str) -> None:
        """Verify submit() raises ForgeAPIError on 409 Conflict."""
        respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(409, json={"error": "This repository has already been submitted"})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        with pytest.raises(ForgeAPIError) as exc_info:
            client.submit("https://github.com/owner/repo")
        assert exc_info.value.status_code == 409
        assert "already" in str(exc_info.value).lower()

    @respx.mock
    def test_submit_raises_on_500(self, mock_forge_url: str) -> None:
        """Verify submit() raises ForgeAPIError on server error."""
        respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(500, json={"error": "Internal Server Error"})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        with pytest.raises(ForgeAPIError) as exc_info:
            client.submit("https://github.com/owner/repo")
        assert exc_info.value.status_code == 500


class TestForgeClientGetSubmissions:
    """Test ForgeClient.get_submissions() at the HTTP transport layer."""

    @respx.mock
    def test_get_submissions_sends_get_request(self, mock_forge_url: str) -> None:
        """Verify get_submissions() sends GET to /api/submissions."""
        route = respx.get(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(200, json=[{"id": "sub-1"}, {"id": "sub-2"}])
        )

        client = ForgeClient(token="test-token-123", forge_url=mock_forge_url)
        client.get_submissions()

        assert route.called
        assert _get_request(route).method == "GET"

    @respx.mock
    def test_get_submissions_sends_auth_header(self, mock_forge_url: str) -> None:
        """Verify get_submissions() includes Bearer token."""
        route = respx.get(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(200, json=[])
        )

        client = ForgeClient(token="my-token", forge_url=mock_forge_url)
        client.get_submissions()

        assert _get_request(route).headers["authorization"] == "Bearer my-token"

    @respx.mock
    def test_get_submissions_parses_list_response(self, mock_forge_url: str) -> None:
        """Verify get_submissions() returns parsed list."""
        respx.get(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(
                200,
                json=[
                    {"id": "sub-1", "status": "pending"},
                    {"id": "sub-2", "status": "approved"},
                ],
            )
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        result = client.get_submissions()

        assert len(result) == 2
        assert result[0]["id"] == "sub-1"
        assert result[1]["status"] == "approved"

    @respx.mock
    def test_get_submissions_raises_on_403(self, mock_forge_url: str) -> None:
        """Verify get_submissions() raises ForgeAPIError on 403 Forbidden."""
        respx.get(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(403, json={"error": "Forbidden"})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        with pytest.raises(ForgeAPIError) as exc_info:
            client.get_submissions()
        assert exc_info.value.status_code == 403

    @respx.mock
    def test_get_submissions_raises_on_500(self, mock_forge_url: str) -> None:
        """Verify get_submissions() raises ForgeAPIError on server error."""
        respx.get(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(500, json={"error": "Internal Server Error"})
        )

        client = ForgeClient(token="test-token", forge_url=mock_forge_url)
        with pytest.raises(ForgeAPIError) as exc_info:
            client.get_submissions()
        assert exc_info.value.status_code == 500
