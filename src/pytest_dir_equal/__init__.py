from typing import TYPE_CHECKING

import pytest

from ._version import __version__

pytest.register_assert_rewrite("pytest_dir_equal.plugin")

from .plugin import DEFAULT_IGNORES, DiffRepr, DirDiff, assert_dir_equal  # noqa: E402

if TYPE_CHECKING:
    from .plugin import AssertDirEqual
