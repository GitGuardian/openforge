from __future__ import annotations

import os
from pathlib import Path

import pytest

from openforge.validation import validate_name, validate_path_containment


class TestValidateName:
    """Tests for name sanitization."""

    def test_valid_simple_name(self) -> None:
        assert validate_name("lint") == "lint"

    def test_valid_with_hyphens(self) -> None:
        assert validate_name("my-skill") == "my-skill"

    def test_valid_with_underscores(self) -> None:
        assert validate_name("my_skill") == "my_skill"

    def test_valid_with_digits(self) -> None:
        assert validate_name("skill42") == "skill42"

    def test_valid_mixed(self) -> None:
        assert validate_name("My-Skill_v2") == "My-Skill_v2"

    def test_valid_single_char(self) -> None:
        assert validate_name("x") == "x"

    def test_valid_max_length(self) -> None:
        name = "a" * 64
        assert validate_name(name) == name

    def test_invalid_empty(self) -> None:
        with pytest.raises(ValueError, match="Invalid name"):
            validate_name("")

    def test_invalid_too_long(self) -> None:
        with pytest.raises(ValueError, match="Invalid name"):
            validate_name("a" * 65)

    def test_invalid_slash(self) -> None:
        with pytest.raises(ValueError, match="Invalid name"):
            validate_name("foo/bar")

    def test_invalid_dot_dot(self) -> None:
        with pytest.raises(ValueError, match="Invalid name"):
            validate_name("..")

    def test_invalid_spaces(self) -> None:
        with pytest.raises(ValueError, match="Invalid name"):
            validate_name("my skill")

    def test_invalid_dot(self) -> None:
        with pytest.raises(ValueError, match="Invalid name"):
            validate_name("foo.bar")

    def test_invalid_special_chars(self) -> None:
        with pytest.raises(ValueError, match="Invalid name"):
            validate_name("foo@bar")

    def test_custom_kind_in_error(self) -> None:
        with pytest.raises(ValueError, match="Invalid plugin name"):
            validate_name("bad name", kind="plugin name")


class TestValidatePathContainment:
    """Tests for path containment checks."""

    def test_valid_child_within_parent(self, tmp_path: Path) -> None:
        child = tmp_path / "subdir" / "file.txt"
        child.parent.mkdir(parents=True, exist_ok=True)
        child.touch()
        validate_path_containment(child, tmp_path)  # should not raise

    def test_valid_nested_child(self, tmp_path: Path) -> None:
        child = tmp_path / "a" / "b" / "c"
        child.mkdir(parents=True)
        validate_path_containment(child, tmp_path)  # should not raise

    def test_escape_with_dotdot(self, tmp_path: Path) -> None:
        parent = tmp_path / "sandbox"
        parent.mkdir()
        child = parent / ".." / ".." / "etc"
        with pytest.raises(ValueError, match="Path escape detected"):
            validate_path_containment(child, parent)

    def test_escape_absolute(self, tmp_path: Path) -> None:
        parent = tmp_path / "sandbox"
        parent.mkdir()
        child = Path("/tmp/evil")
        with pytest.raises(ValueError, match="Path escape detected"):
            validate_path_containment(child, parent)

    def test_symlink_escape(self, tmp_path: Path) -> None:
        """Symlink pointing outside the parent should be caught."""
        parent = tmp_path / "sandbox"
        parent.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        link = parent / "sneaky"
        link.symlink_to(outside)
        with pytest.raises(ValueError, match="Path escape detected"):
            validate_path_containment(link, parent)

    def test_parent_equals_child(self, tmp_path: Path) -> None:
        """A path that is exactly the parent should be valid."""
        validate_path_containment(tmp_path, tmp_path)  # should not raise
