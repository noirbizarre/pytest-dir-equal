from __future__ import annotations

import fnmatch
import os
import shutil

from itertools import filterfalse
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Iterator,
    TypeVar,
    cast,
)

from pygments.styles import get_style_by_name
from pygments.token import Generic
from pygments.util import ClassNotFound
from syrupy.data import (
    Snapshot,
    SnapshotCollection,
    SnapshotCollections,
)
from syrupy.location import PyTestLocation
from syrupy.utils import in_snapshot_dir

from .base import AbstractSyrupyExtension

if TYPE_CHECKING:
    from syrupy.types import (
        PropertyFilter,
        PropertyMatcher,
    )

    try:
        from pygments.lexer import (
            Lexer,
            LexerMeta,
        )
        from pygments.style import Style
    except Exception:
        Style = Lexer = LexerMeta = Any  # type: ignore


T = TypeVar("T")

GITKEEPER = "syrupy.gitkeep"
"""Filename of the git keeper file for empty directories"""


def _filter(flist: list[Any], skip: list[str]) -> list[Any]:
    for pattern in skip:
        flist = list(filterfalse(fnmatch.filter(flist, pattern).__contains__, flist))
    return flist


def _style() -> type[Style]:
    try:
        style = get_style_by_name(os.getenv("PYTEST_THEME", "default"))
    except ClassNotFound:
        style = get_style_by_name("default")

    class SyrupyStyle(style):
        styles = {
            **style.styles,
            Generic.Inserted: "bg:#d7ffff #005f5f",
            Generic.Deleted: "bg:#ffd7ff #870087",
        }

    return SyrupyStyle


class PathSnapshotExtension(AbstractSyrupyExtension):
    def serialize(  # type: ignore[override]
        self,
        data: Path,
        *,
        exclude: PropertyFilter | None = None,
        include: PropertyFilter | None = None,
        matcher: PropertyMatcher | None = None,
    ) -> SerializedPath:
        if not isinstance(data, (str, Path)):
            raise ValueError(f"{data} is not a Path-like")
        if isinstance(data, str):
            data = Path(data)
        return SerializedPath(data)

    def discover_snapshots(self, *, test_location: PyTestLocation) -> SnapshotCollections:
        """
        Returns all snapshot collections in test site
        """
        discovered: SnapshotCollections = SnapshotCollections()
        snapshots = Path(self.dirname(test_location=test_location)) / test_location.basename

        for path in snapshots.glob("*"):
            if (
                not in_snapshot_dir(path)
                # or not path.is_dir()
                or path.name.startswith(".")
            ):
                continue
            if path.stem.startswith(test_location.testname):
                snapshot_collection = SnapshotCollection(location=str(path))
                snapshot_collection.add(Snapshot(name=path.stem))
                discovered.add(snapshot_collection)

        return discovered

    def delete_snapshots(self, *, snapshot_location: str, snapshot_names: set[str]) -> None:
        """
        Remove snapshots from a snapshot file.
        If the snapshot file will be empty remove the entire file.
        """
        if (path := Path(snapshot_location)).is_dir():
            shutil.rmtree(snapshot_location)
        else:
            path.unlink()

    def _read_snapshot_collection(self, *, snapshot_location: str) -> SnapshotCollection:
        return SnapshotCollection("anywhere")  # Not used, here to comply with @bastractmethod

    def _read_snapshot_data_from_location(  # type: ignore[override]
        self, *, snapshot_location: str, snapshot_name: str, session_id: str
    ) -> SerializedPath | None:
        """
        Get only the snapshot data from location for assertion
        """
        path = Path(snapshot_location) / snapshot_name
        if not path.exists():
            return None
        return SerializedPath(path)

    @classmethod
    def _write_snapshot_collection(cls, *, snapshot_collection: SnapshotCollection) -> None:
        """
        Adds the snapshot data to the snapshots in collection location
        """
        snapshot = list(snapshot_collection._snapshots.values())[0]
        path = cast(Path, snapshot.data.path)
        location = Path(snapshot_collection.location)
        target = location / snapshot.name
        if path.is_dir():
            empty_dirs = []

            def ignore(dir: Path, files: list[str]):
                if not files:
                    empty_dirs.append(dir)
                return set()

            shutil.copytree(snapshot.data.path, target, ignore=ignore)
            for empty in empty_dirs:
                rel_path = Path(empty).relative_to(snapshot.data.path)
                (location / rel_path / GITKEEPER).write_text("")
        else:
            shutil.copy(snapshot.data.path, target)

    def diff_lines(
        self,
        serialized_data: SerializedPath,  # type: ignore[override]
        snapshot_data: SerializedPath,  # type: ignore[override]
    ) -> Iterator[str]:
        # ctx = Ctx(self._context_line_max, super().__diff_lines)
        yield from serialized_data.diff_lines(snapshot_data)
