# SPDX-License-Identifier: Apache-2.0
"""Integration tests for publish command — ForgeClient.submit() transport layer.

publish_command calls get_auth_token() then ForgeClient(token=token).submit().
ForgeClient uses httpx, so we use respx to intercept requests.
"""

from __future__ import annotations

import json
from typing import cast

import httpx
import respx
from httpx import Response

from openforge.api_client import ForgeClient


class TestPublishIntegration:
    """Test publish flow via ForgeClient at the HTTP transport layer."""

    @respx.mock
    def test_submit_posts_to_submissions_endpoint(self, mock_forge_url: str) -> None:
        """submit() POSTs to /api/submissions."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-1", "status": "pending"})
        )

        client = ForgeClient(token="test-token-123", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo")

        assert route.called

    @respx.mock
    def test_submit_sends_description_when_provided(self, mock_forge_url: str) -> None:
        """submit() includes description field in body when provided."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-2", "status": "pending"})
        )

        client = ForgeClient(token="tok", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo", "My plugin description")

        request = cast(httpx.Request, route.calls[0].request)
        body = json.loads(request.content)
        assert body.get("description") == "My plugin description"

    @respx.mock
    def test_submit_omits_description_when_not_provided(self, mock_forge_url: str) -> None:
        """submit() without description omits the description field."""
        route = respx.post(f"{mock_forge_url}/api/submissions").mock(
            return_value=Response(201, json={"id": "sub-3", "status": "pending"})
        )

        client = ForgeClient(token="tok", forge_url=mock_forge_url)
        client.submit("https://github.com/owner/repo")

        request = cast(httpx.Request, route.calls[0].request)
        body = json.loads(request.content)
        # description should be absent when not provided
        assert "description" not in body
