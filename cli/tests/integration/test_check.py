# SPDX-License-Identifier: Apache-2.0
"""Integration tests for check command — staleness detection.

Tests check_entry_staleness() by patching openforge.check._git_ls_remote.
Uses real LockEntry instances (not dicts) as required by the type signature.
Results are accessed via attributes: .is_outdated, .remote_sha, .error.
"""

from __future__ import annotations

from unittest.mock import patch

from openforge.check import check_entry_staleness
from openforge.types import ContentType, LockEntry, SourceType


def _make_entry(
    source: str = "https://github.com/owner/repo",
    source_type: SourceType = SourceType.GITHUB,
    git_sha: str = "abc123",
    git_url: str = "https://github.com/owner/repo",
) -> LockEntry:
    """Build a minimal LockEntry for testing."""
    return LockEntry(
        type=ContentType.SKILL,
        source=source,
        source_type=source_type,
        git_url=git_url,
        git_sha=git_sha,
        skills=(),
        agents_installed=(),
        installed_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


class TestCheckEntryStaleness:
    """Test check_entry_staleness() — the core staleness logic."""

    def test_entry_is_current_when_sha_matches(self) -> None:
        """Entry is not outdated when installed SHA matches remote SHA."""
        sha = "abc123def456"
        entry = _make_entry(git_sha=sha)

        with patch("openforge.check._git_ls_remote", return_value=sha):
            result = check_entry_staleness("my-plugin", entry)

        assert not result.is_outdated
        assert result.remote_sha == sha

    def test_entry_is_outdated_when_sha_differs(self) -> None:
        """Entry is outdated when installed SHA differs from remote SHA."""
        installed_sha = "abc123"
        remote_sha = "def456"
        entry = _make_entry(git_sha=installed_sha)

        with patch("openforge.check._git_ls_remote", return_value=remote_sha):
            result = check_entry_staleness("my-plugin", entry)

        assert result.is_outdated
        assert result.remote_sha == remote_sha

    def test_local_source_is_skipped(self) -> None:
        """Local source entries are skipped — no remote to compare."""
        entry = _make_entry(
            source="/Users/someone/local/repo",
            source_type=SourceType.LOCAL,
        )

        result = check_entry_staleness("local-plugin", entry)

        assert not result.is_outdated
        assert result.error is not None
        assert "local" in result.error.lower()
