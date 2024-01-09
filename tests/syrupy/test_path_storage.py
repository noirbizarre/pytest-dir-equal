from __future__ import annotations

from pathlib import Path

import pytest

from syrupy.assertion import SnapshotAssertion
from syrupy.data import Snapshot, SnapshotCollection

from pytest_dir_equal.syrupy import GITKEEPER, SerializedPath


@pytest.fixture
def tested(tmp_path: Path) -> SerializedPath:
    return SerializedPath(tmp_path / "tested")


@pytest.fixture
def collection(tmp_path: Path, tested: SerializedPath) -> SnapshotCollection:
    path = tmp_path / "snapshot_collection"
    collection = SnapshotCollection(str(path))
    collection.add(Snapshot(name=tested.path.stem, data=tested))
    return collection


def test_write_empty_dir(
    tested: SerializedPath,
    collection: SnapshotCollection,
    snapshot: SnapshotAssertion,
):
    tested.path.mkdir()
    snapshot.extension._write_snapshot_collection(snapshot_collection=collection)
    location = Path(collection.location)
    assert location.exists()
    assert location.is_dir()
    assert (location / GITKEEPER).exists()


def test_write_an_empty_file(
    tested: SerializedPath,
    collection: SnapshotCollection,
    snapshot: SnapshotAssertion,
):
    tested.path.write_text("")
    snapshot.extension._write_snapshot_collection(snapshot_collection=collection)
    location = Path(collection.location)
    assert location.exists()
    assert location.is_file()


def test_write_multiple_files(
    tested: SerializedPath,
    collection: SnapshotCollection,
    snapshot: SnapshotAssertion,
):
    tested.path.mkdir()
    for i in range(3):
        (tested.path / f"text{i}.file").write_text(f"content {i}")
    snapshot.extension._write_snapshot_collection(snapshot_collection=collection)
    location = Path(collection.location)
    assert location.exists()
    assert location.is_dir()
    for i in range(3):
        assert (location / f"text{i}.file").read_text() == f"content {i}"
    assert not (location / GITKEEPER).exists()


def test_write_nested_file_and_dirs(
    tested: SerializedPath,
    collection: SnapshotCollection,
    snapshot: SnapshotAssertion,
):
    tested.path.mkdir()
    nested = tested.path / "nested"
    nested.mkdir()
    for i in range(3):
        (nested / f"text{i}.file").write_text(f"content {i}")
    (nested / "empty").mkdir()
    snapshot.extension._write_snapshot_collection(snapshot_collection=collection)
    location = Path(collection.location)
    assert location.exists()
    assert location.is_dir()
    nested_location = location / "nested"
    assert nested_location.exists()
    assert nested_location.is_dir()
    for i in range(3):
        assert (nested_location / f"text{i}.file").read_text() == f"content {i}"
    assert not (nested_location / GITKEEPER).exists()
    empty = nested_location / "empty"
    assert empty.exists()
    assert empty.is_dir()
    assert (empty / GITKEEPER).exists()


def test_delete_file(collection: SnapshotCollection, snapshot: SnapshotAssertion):
    location = Path(collection.location)
    location.write_text("I'm a file")

    snapshot.extension.delete_snapshots(
        snapshot_location=collection.location, snapshot_names={"whatever"}
    )

    assert not location.exists()


def test_delete_dir(collection: SnapshotCollection, snapshot: SnapshotAssertion):
    location = Path(collection.location)
    location.mkdir()
    file = location / "file"
    file.write_text("I'm a file")

    snapshot.extension.delete_snapshots(
        snapshot_location=collection.location,
        snapshot_names=set(),
    )

    assert not location.exists()


def test_delete_nested_dirs(collection: SnapshotCollection, snapshot: SnapshotAssertion):
    location = Path(collection.location)
    location.mkdir()
    nested = location / "nested"
    nested.mkdir()
    file = nested / "file"
    file.write_text("I'm a file")

    snapshot.extension.delete_snapshots(
        snapshot_location=collection.location,
        snapshot_names=set(),
    )

    assert not location.exists()
