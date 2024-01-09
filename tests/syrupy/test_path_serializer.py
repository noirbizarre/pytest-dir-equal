from __future__ import annotations

import sys

from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.mark.structures import MarkDecorator
    from syrupy.assertion import SnapshotAssertion


# pytestmark = pytest.mark.usefixtures("colorized")


@pytest.fixture(params=(True, False))
def colorized(request, monkeypatch):
    if not request.param:
        monkeypatch.setitem(sys.modules, "pygments", None)
    return request.param


@pytest.fixture
def testdir(tmp_path: Path) -> Path:
    tmp_path.joinpath("file").write_text("content\n")
    return tmp_path


def should_fail(reason: str) -> MarkDecorator:
    return pytest.mark.xfail(reason=f"Should fail: {reason}", raises=AssertionError, strict=True)


def test_flat_directory(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot


def test_text_file(tmp_path: Path, snapshot: SnapshotAssertion):
    file = tmp_path / "file"
    file.write_text("content\n")
    assert file == snapshot


def test_path_as_str(tmp_path: Path, snapshot: SnapshotAssertion):
    file = tmp_path / "file"
    file.write_text("content\n")
    assert str(file) == snapshot


def test_text_file_with_syntax(tmp_path: Path, snapshot: SnapshotAssertion, colorized: bool):
    file = tmp_path / "file.json"
    file.write_text("{}\n")
    assert file == snapshot


def test_binary_file(tmp_path: Path, snapshot: SnapshotAssertion, colorized: bool):
    file = tmp_path / "file.bin"
    file.write_bytes(b"\x00")
    assert file == snapshot


def test_nested_directories(testdir: Path, snapshot: SnapshotAssertion):
    subdir = testdir / "sub"
    subdir.mkdir()
    subdir.joinpath("file").write_text("sub directory file\n")
    nested = subdir / "nested"
    nested.mkdir()
    nested.joinpath("file").write_text("nested directory file\n")
    assert testdir == snapshot


def test_multiple_directories(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot

    testdir.joinpath("extra").write_text("extra\n")
    assert testdir == snapshot


def test_empty_directory(tmp_path: Path, snapshot: SnapshotAssertion):
    assert tmp_path == snapshot


@should_fail("The empty tested directory should not match the snapshot")
def test_empty_tested_directory(tmp_path: Path, snapshot: SnapshotAssertion):
    assert tmp_path == snapshot


@should_fail("The tested directory should not match the empty snapshot")
def test_empty_snapshot_directory(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot


@pytest.mark.parametrize("value", ("1st", "2nd"))
def test_parametrize(testdir: Path, snapshot: SnapshotAssertion, value: str):
    (testdir / "file").write_text(f"{value}\n")
    assert testdir == snapshot


@should_fail("The snapshot has an extra files")
def test_fail_if_has_extra_file(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot


@should_fail("The snapshot is missing files")
def test_fail_if_is_missing_files(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot


@should_fail("The snapshot files are different")
def test_fail_if_files_differs(testdir: Path, snapshot: SnapshotAssertion):
    assert testdir == snapshot


@should_fail("The snapshot file is different")
@pytest.mark.usefixtures("colorized")
def test_fail_if_file_differ(tmp_path: Path, snapshot: SnapshotAssertion):
    file = tmp_path / "file.json"
    file.write_text("{}\n")
    assert file == snapshot


@should_fail("The snapshot file is different")
@pytest.mark.usefixtures("colorized")
def test_fail_if_binary_file_size_differ(tmp_path: Path, snapshot: SnapshotAssertion):
    file = tmp_path / "file.bin"
    file.write_bytes(b"\x00\x00")
    assert file == snapshot


@should_fail("The snapshot file is different")
@pytest.mark.usefixtures("colorized")
def test_fail_if_binary_file_content_differ(tmp_path: Path, snapshot: SnapshotAssertion):
    file = tmp_path / "file.bin"
    file.write_bytes(b"\x90")
    assert file == snapshot


@should_fail("The snapshot files are different")
def test_file_formats(tmp_path: Path, snapshot: SnapshotAssertion):
    (tmp_path / "test.json").write_text("{\n}")
    (tmp_path / "test.yaml").write_text(
        dedent(
            """\
        key: value
        other: changed value
        last: new value
        new: key
    """
        )
    )
    (tmp_path / "file.added").write_text("I am not in the snapshot")
    assert tmp_path == snapshot
