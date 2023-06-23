from __future__ import annotations

import filecmp
import fnmatch
import os
import sys

from dataclasses import dataclass
from io import StringIO
from itertools import filterfalse
from pathlib import Path
from typing import TYPE_CHECKING

import icdiff

from _pytest._code.code import TerminalRepr
from _pytest._io import TerminalWriter, get_terminal_width

if TYPE_CHECKING:
    if sys.version_info >= (3, 8):
        from typing import Protocol
    else:
        from typing_extensions import Protocol


COLS = get_terminal_width()
LEFT_MARGIN = 10
GUTTER = 2
MARGINS = LEFT_MARGIN + GUTTER + 1
DIFF_WIDTH = COLS - MARGINS

EXPECTED_HEADER = " expected "
ACTUAL_HEADER = " actual "


DEFAULT_IGNORES = filecmp.DEFAULT_IGNORES


@dataclass
class DiffRepr(TerminalRepr):
    name: str

    def actual_lines(self) -> list[str]:
        raise NotImplementedError()

    def expected_lines(self) -> list[str]:
        raise NotImplementedError()

    def toterminal(self, tw: TerminalWriter) -> None:
        differ = icdiff.ConsoleDiff(
            tabsize=2,
            cols=DIFF_WIDTH,
            highlight=True,
            truncate=True,
            line_numbers=True,
        )
        if not tw.hasmarkup:
            # colorization is disabled in Pytest - either due to the terminal not
            # supporting it or the user disabling it. We should obey, but there is
            # no option in icdiff to disable it, so we replace its colorization
            # function with a no-op
            differ.colorize = lambda string: string
            color_off = ""
        else:
            color_off = icdiff.color_codes["none"]

        line_length = COLS - LEFT_MARGIN
        tw.line(f"💥 {self.name} files are different, see the diff below 👇")
        diff_header = f"[ {self.name} ]"
        half_header = int((line_length - len(diff_header)) / 2)
        halt_left_header = int((half_header - len(EXPECTED_HEADER)) / 2)
        left_header = halt_left_header * "-" + EXPECTED_HEADER + halt_left_header * "-"
        halt_right_header = int((half_header - len(ACTUAL_HEADER)) / 2)
        right_header = halt_right_header * "-" + ACTUAL_HEADER + halt_right_header * "-"
        tw.line(left_header + diff_header + right_header)

        lines = differ.make_table(self.expected_lines(), self.actual_lines(), context=True)
        for line in lines:
            tw.line(color_off + line)

        diff_footer = f"[ end of {self.name} diff ]"
        half_footer = int((line_length - len(diff_footer)) / 2)
        tw.line(half_footer * "-" + diff_footer + half_footer * "-")


@dataclass
class ReprDiffError(DiffRepr):
    expected: Path
    actual: Path

    def actual_lines(self) -> list[str]:
        return self.actual.read_text().splitlines()

    def expected_lines(self) -> list[str]:
        return self.expected.read_text().splitlines()


def _filter(flist, skip):
    for pattern in skip:
        flist = list(filterfalse(fnmatch.filter(flist, pattern).__contains__, flist))
    return flist


class DirDiff(filecmp.dircmp):
    def __bool__(self) -> bool:
        return any(
            (self.left_only, self.right_only, self.common_funny, self.diff_files, self.funny_files)
        ) or any(value for value in self.subdirs.values())

    def phase0(self):  # Compare everything except common subdirectories
        self.left_list = _filter(os.listdir(self.left), self.hide + self.ignore)
        self.right_list = _filter(os.listdir(self.right), self.hide + self.ignore)
        self.left_list.sort()
        self.right_list.sort()

    def to_terminal(self, tw: TerminalWriter, prefix: Path | None = None):
        prefix = prefix or Path("")
        for name in self.diff_files:
            ReprDiffError(
                prefix / name, expected=Path(self.right) / name, actual=Path(self.left) / name
            ).toterminal(tw)
        for name in self.left_only:
            tw.line(f"🚫 {prefix / name} file is present but not expected in the actual directory")
        for name in self.right_only:
            tw.line(f"⛔ {prefix / name} is missing from the actual directory")
        for name, sub in self.subdirs.items():
            prefix = Path(name) if not prefix else (prefix / name)
            sub.to_terminal(tw, prefix=prefix)  # type: ignore


DirDiff.methodmap = DirDiff.methodmap.copy()
DirDiff.methodmap.update(left_list=DirDiff.phase0, right_list=DirDiff.phase0)  # type: ignore


def assert_dir_equal(tested: Path, ref: Path | str, ignore: list[str] | None = None):
    __tracebackhide__ = True
    diff = DirDiff(tested, ref, ignore=ignore)
    if diff:
        out = StringIO()
        tw = TerminalWriter(out)
        tw.hasmarkup = True
        tw.line("❌ Some files are different")
        diff.to_terminal(tw)
        raise AssertionError(out.getvalue())


if TYPE_CHECKING:

    class AssertDirEqual(Protocol):
        def __call__(self, tested: Path, ref: Path | str, ignore: list[str] | None = None):
            ...
