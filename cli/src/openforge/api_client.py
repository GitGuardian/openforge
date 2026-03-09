# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from typing import Any

import httpx


class ForgeAPIError(Exception):
    """Raised when a Forge API call fails."""

    def __init__(self, message: str, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


def _get_forge_url() -> str:
    """Read forge URL from config."""
    from openforge.config_file import load_config

    return load_config().forge_url


class ForgeClient:
    """HTTP client for The Forge API with authentication."""

    def __init__(
        self,
        token: str,
        forge_url: str | None = None,
    ) -> None:
        self.token = token
        self.forge_url = forge_url or _get_forge_url()

    def _headers(self) -> dict[str, str]:
        """Return request headers with auth token."""
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, *, json: dict[str, Any] | None = None) -> httpx.Response:
        """POST to a Forge API endpoint."""
        response = httpx.post(
            f"{self.forge_url}{path}",
            json=json,
            headers=self._headers(),
            timeout=30.0,
        )
        if response.status_code >= 400:
            try:
                body = response.json()
                msg = body.get("error", response.text)
            except Exception:  # noqa: BLE001
                msg = response.text
            raise ForgeAPIError(str(msg), status_code=response.status_code)
        return response

    def _get(self, path: str) -> httpx.Response:
        """GET from a Forge API endpoint."""
        response = httpx.get(
            f"{self.forge_url}{path}",
            headers=self._headers(),
            timeout=30.0,
        )
        if response.status_code >= 400:
            try:
                body = response.json()
                msg = body.get("error", response.text)
            except Exception:  # noqa: BLE001
                msg = response.text
            raise ForgeAPIError(str(msg), status_code=response.status_code)
        return response

    def submit(self, git_url: str, description: str | None = None) -> dict[str, Any]:
        """Submit a plugin to The Forge for review."""
        payload: dict[str, Any] = {"gitUrl": git_url}
        if description is not None:
            payload["description"] = description
        response = self._post("/api/submissions", json=payload)
        result: dict[str, Any] = response.json()
        return result

    def get_submissions(self) -> list[dict[str, Any]]:
        """Get the current user's submissions."""
        response = self._get("/api/submissions")
        result: list[dict[str, Any]] = response.json()
        return result
