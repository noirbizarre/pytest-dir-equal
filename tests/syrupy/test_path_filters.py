from pathlib import Path

import pytest

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import paths


@pytest.fixture
def testdir(tmp_path: Path):
    tmp_path.joinpath("root.file").touch()
    tmp_path.joinpath("another.one").touch()
    subdir = tmp_path / "sub"
    subdir.mkdir()
    subdir.joinpath("some.file").touch()
    nested = subdir / "nested"
    nested.mkdir()
    nested.joinpath("another.file").touch()
    return tmp_path


def test_exclude(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot


def test_exclude_file(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot(exclude=paths("root.file"))


def test_exclude_glob_pattern(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot(exclude=paths("**/*.file"))


def test_exclude_multiple(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot(exclude=paths("**/another.*", "root.file"))


def test_include_file(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot(include=paths("root.file"))


def test_include_glob_pattern(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot(include=paths("**/*.file"))


def test_include_multiple(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot(include=paths("**/another.*", "root.file"))


def test_mix_include_exclude(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot(include=paths("**/*.file"), exclude=paths("**/another.*"))
