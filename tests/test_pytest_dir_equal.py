from __future__ import annotations

import pytest_dir_equal


def test_expose_version():
    assert pytest_dir_equal.__version__
