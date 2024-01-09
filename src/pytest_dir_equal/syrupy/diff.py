from __future__ import annotations

import difflib
import filecmp
import fnmatch
import os
import re

from dataclasses import dataclass
from functools import cached_property
from itertools import filterfalse
from pathlib import Path
from typing import (
    Any,
    Iterator,
    Protocol,
    TypeVar,
    cast,
)

from syrupy.terminal import (
    received_diff_style,
    received_style,
    reset,
    snapshot_diff_style,
    snapshot_style,
)

from .const import GITKEEPER
from .highlight import highlight_diff, highlight_file

T = TypeVar("T")

RE_ANSI = re.compile(r"\x1b\[\d+(;\d+){0,3}m")


class Diff(Protocol):
    def diff_lines(self) -> Iterator[str]:
        ...


def _common_suffix(left: Path, right: Path) -> str:
    left_parts = reversed(left.parts)
    right_parts = reversed(right.parts)
    common = []
    for left_part, right_part in zip(left_parts, right_parts):
        if not left_part == right_part:
            break
        common.append(left_part)
    return os.path.sep.join(reversed(common))


def added_line_wdiff(
    a: str,
    b: str,
) -> str:
    matcher = difflib.SequenceMatcher(None, a, b)

    def process_tag(tag, i1, i2, j1, j2):
        if tag in ("replace", "insert"):
            return f"{{+{b[j1:j2]}+}}"
        if tag == "delete":
            return ""
        if tag == "equal":
            return a[i1:i2]
        assert False, "Unknown tag %r" % tag

    return "".join(process_tag(*t) for t in matcher.get_opcodes())


def removed_line_wdiff(
    a: str,
    b: str,
) -> str:
    matcher = difflib.SequenceMatcher(None, a, b)

    def process_tag(tag, i1, i2, j1, j2):
        if tag in ("replace", "delete"):
            return f"[-{a[i1:i2]}-]"
        if tag == "equal":
            return a[i1:i2]
        if tag == "insert":
            return ""
        assert False, "Unknown tag %r" % tag

    return "".join(process_tag(*t) for t in matcher.get_opcodes())


def wdiff(a: list[str], b: list[str], fromfile="", tofile="", n=3, lineterm="\n"):
    started = False
    for group in difflib.SequenceMatcher(None, a, b).get_grouped_opcodes(n):
        if not started:
            started = True
            yield f"--- {fromfile}{lineterm}"
            yield f"+++ {tofile}{lineterm}"

        first, last = group[0], group[-1]
        file1_range = difflib._format_range_unified(first[1], last[2])
        file2_range = difflib._format_range_unified(first[3], last[4])
        yield f"@@ -{file1_range} +{file2_range} @@{lineterm}"

        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for line in a[i1:i2]:
                    yield " " + line
                continue
            if tag == "delete":
                for line in a[i1:i2]:
                    yield f"- {line}"
            if tag in {"replace"}:
                for line_a, line_b in zip(a[i1:i2], b[j1:j2]):
                    yield f"- {removed_line_wdiff(line_a, line_b)}"
            if tag == "insert":
                for line in b[j1:j2]:
                    yield f"+ {line}"
            if tag == "replace":
                for line_a, line_b in zip(a[i1:i2], b[j1:j2]):
                    yield f"+ {added_line_wdiff(line_a, line_b)}"


DEFAULT_IGNORES = filecmp.DEFAULT_IGNORES


@dataclass
class FileDiff:
    received: Path
    snapshot: Path

    @cached_property
    def name(self) -> str:
        return (
            _common_suffix(self.received, self.snapshot)
            or f"{self.received.name}<>{self.snapshot.name}"
        )

    def __bool__(self) -> bool:
        return self.received.read_bytes() != self.snapshot.read_bytes()

    def __repr__(self) -> str:
        return f"FileDiff({self.name})"

    def _load(self, file: Path) -> str:
        """Load the given file and highlight if we have markup support."""
        return highlight_file(self.name, file.read_text())

    def diff_lines(self) -> Iterator[str]:
        try:
            received = self._load(self.received)
            snapshot = self._load(self.snapshot)
        except UnicodeDecodeError:
            # Can't load, perform a binary diff
            if self.received.stat().st_size != self.snapshot.stat().st_size:
                yield reset(f"🚫 {self.name}: binary files sizes differs")
            else:
                yield reset(f"🚫 {self.name}: binary files content differs")
            return

        diff = wdiff(
            snapshot.splitlines(keepends=True),
            received.splitlines(keepends=True),
            f"<snapshot>/{self.name}",
            f"<received>/{self.name}",
        )

        for line in highlight_diff(diff):
            yield reset(line.rstrip("\n"))


def _filter(flist: list[Any], skip: list[str]) -> list[Any]:
    for pattern in skip:
        flist = list(filterfalse(fnmatch.filter(flist, pattern).__contains__, flist))
    return flist


class DirDiff(filecmp.dircmp[Any]):
    ignore: list[str]
    hide: list[str]

    EXCLUDED: list[str] = [  # Always ignored files (internals)
        GITKEEPER,
    ]

    def __repr__(self) -> str:
        return (
            f"DirDiff({self.left_only=}, {self.right_only=}, {self.common_funny=}, "
            f"{self.diff_files=}, {self.funny_files=} {self.subdirs=})"
        )

    def __bool__(self) -> bool:
        return any(
            (
                self.left_only,
                self.right_only,
                self.common_funny,
                self.diff_files,
                self.funny_files,
            )
        ) or any(value for value in self.subdirs.values())

    def phase0(self) -> None:  # Compare everything except common subdirectories
        self.left_list = _filter(os.listdir(self.left), self.hide + self.ignore + self.EXCLUDED)
        self.right_list = _filter(os.listdir(self.right), self.hide + self.ignore + self.EXCLUDED)
        self.left_list.sort()
        self.right_list.sort()

    def phase3(self) -> None:  # Find out differences between common files
        xx = filecmp.cmpfiles(self.left, self.right, self.common_files, False)
        self.same_files, self.diff_files, self.funny_files = xx

    def diff_lines(self, prefix: Path | None = None) -> Iterator[str]:
        prefix = prefix or Path("")
        for name in self.diff_files:
            diff = FileDiff(
                snapshot=Path(self.right) / name,
                received=Path(self.left) / name,
            )
            yield from diff.diff_lines()
        for name in self.left_only:
            yield reset(
                received_style(f"+++ added: <received>/{received_diff_style(prefix / name)}")
            )
            yield reset(snapshot_style("--- N/A"))
        for name in self.right_only:
            yield reset(received_style("+++ N/A"))
            yield reset(
                snapshot_style(f"--- missing: <snapshot>/{snapshot_diff_style(prefix / name)}")
            )
        for name, sub in self.subdirs.items():
            prefix = Path(name) if not prefix else (prefix / name)
            yield from cast(DirDiff, sub).diff_lines(prefix)  # type[attr-defined]


DirDiff.methodmap = DirDiff.methodmap.copy()
DirDiff.methodmap.update(
    left_list=DirDiff.phase0,  # type: ignore[arg-type]
    right_list=DirDiff.phase0,  # type: ignore[arg-type]
    same_files=DirDiff.phase3,  # type: ignore[arg-type]
    diff_files=DirDiff.phase3,  # type: ignore[arg-type]
    funny_files=DirDiff.phase3,  # type: ignore[arg-type]
)
