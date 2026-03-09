# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx


def test_forge_client_adds_auth_header() -> None:
    """ForgeClient includes Authorization header on requests."""
    from openforge.api_client import ForgeClient

    client = ForgeClient(token="test-token", forge_url="https://example.com")
    assert client._headers()["Authorization"] == "Bearer test-token"


def test_forge_client_submit_posts_to_submissions() -> None:
    """submit() POSTs to /api/submissions with git_url and description."""
    from openforge.api_client import ForgeClient

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": "sub-1",
        "status": "pending",
        "gitUrl": "https://github.com/owner/repo",
    }
    mock_response.raise_for_status = MagicMock()

    client = ForgeClient(token="test-token", forge_url="https://example.com")

    with patch.object(client, "_post", return_value=mock_response):
        result = client.submit("https://github.com/owner/repo", "A great plugin")
        assert result["id"] == "sub-1"
        assert result["status"] == "pending"


def test_forge_client_submit_without_description() -> None:
    """submit() works without a description."""
    from openforge.api_client import ForgeClient

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "sub-1", "status": "pending"}
    mock_response.raise_for_status = MagicMock()

    client = ForgeClient(token="test-token", forge_url="https://example.com")

    with patch.object(client, "_post", return_value=mock_response) as mock_post:
        client.submit("https://github.com/owner/repo")
        call_args = mock_post.call_args
        body = call_args[1]["json"] if "json" in (call_args[1] or {}) else call_args[0][1]
        # description should be None or absent
        assert body.get("description") is None


def test_forge_client_get_submissions() -> None:
    """get_submissions() GETs /api/submissions."""
    from openforge.api_client import ForgeClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": "sub-1", "status": "pending"},
        {"id": "sub-2", "status": "approved"},
    ]
    mock_response.raise_for_status = MagicMock()

    client = ForgeClient(token="test-token", forge_url="https://example.com")

    with patch.object(client, "_get", return_value=mock_response):
        result = client.get_submissions()
        assert len(result) == 2
        assert result[0]["id"] == "sub-1"


def test_forge_client_handles_http_error() -> None:
    """ForgeClient raises on HTTP errors."""
    from openforge.api_client import ForgeAPIError, ForgeClient

    client = ForgeClient(token="test-token", forge_url="https://example.com")

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server Error", request=MagicMock(), response=mock_response
    )

    with patch.object(client, "_post", return_value=mock_response):
        mock_response2 = MagicMock()
        mock_response2.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

    # Test via submit which calls _post internally
    import pytest

    with (
        patch("httpx.post", return_value=mock_response),
        pytest.raises(ForgeAPIError),
    ):
        client.submit("https://github.com/owner/repo")


def test_forge_client_reads_forge_url_from_config(tmp_path: Path) -> None:
    """ForgeClient defaults forge_url from config when not provided."""
    from openforge.api_client import ForgeClient

    with patch("openforge.api_client._get_forge_url", return_value="https://my-forge.example.com"):
        client = ForgeClient(token="test-token")
        assert client.forge_url == "https://my-forge.example.com"
