from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

pytest.register_assert_rewrite("pytest_dir_equal.plugin")

from .plugin import DEFAULT_IGNORES, DiffRepr, DirDiff, assert_dir_equal  # noqa: E402

if TYPE_CHECKING:
    from .plugin import AssertDirEqual


def read_version() -> str:
    try:
        return str(
            version("pytest-dir-equal")
        )  # This is the PEP621 `project.name` not the root package
    except (PackageNotFoundError, ImportError):
        version_file = Path(__file__).parent / "VERSION"
        return version_file.read_text() if version_file.is_file() else "0.0.0.dev"


__version__ = read_version()  # should be failsafe
