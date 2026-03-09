# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for CLI integration tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_forge_url() -> str:
    """Base URL for mock Forge server."""
    return "https://forge.test.local"


@pytest.fixture
def mock_supabase_url() -> str:
    """Base URL for mock Supabase auth."""
    return "https://auth.test.local"
