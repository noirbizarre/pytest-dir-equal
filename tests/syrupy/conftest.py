from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from pytest_dir_equal.syrupy import PathSnapshotExtension

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    return snapshot.use_extension(PathSnapshotExtension)
