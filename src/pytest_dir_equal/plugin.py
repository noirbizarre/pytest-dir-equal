from __future__ import annotations

import filecmp
import fnmatch
import os
import re

from dataclasses import dataclass
from enum import Enum
from functools import cached_property
from io import StringIO
from itertools import filterfalse
from pathlib import Path
from typing import TYPE_CHECKING

import icdiff

from _pytest._code.code import TerminalRepr
from _pytest._io import TerminalWriter, get_terminal_width

if TYPE_CHECKING:
    from typing import Protocol


COLS = get_terminal_width()
LEFT_MARGIN = 10
GUTTER = 2
MARGINS = LEFT_MARGIN + GUTTER
DIFF_WIDTH = COLS - MARGINS

DEFAULT_IGNORES = filecmp.DEFAULT_IGNORES


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class Kind(StrEnum):
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    DIFF = "DIFF"
    TYPE_DIFF = "TYPE_DIFF"


class Icon(StrEnum):
    ADDED = "➕"
    REMOVED = "➖"
    DIFF = "💥"
    DIR = "📁"
    FILE = "📃"
    SYMLINK = "🔗"


class Style(StrEnum):
    ADDED = icdiff.color_codes["green"]
    REMOVED = icdiff.color_codes["red"]
    DIFF = icdiff.color_codes["yellow"]
    NONE = icdiff.color_codes["none"]


def len_no_ansi(string):
    """Get the length of a string without the ANSI codes"""
    return len(
        re.sub(
            r"[\u001B\u009B][\[\]()#;?]*((([a-zA-Z\d]*(;[-a-zA-Z\d\/#&.:=?%@~_]*)*)?\u0007)|((\d{1,4}(?:;\d{0,4})*)?[\dA-PR-TZcf-ntqry=><~]))",
            "",
            string,
        )
    )


@dataclass
class DiffRepr(TerminalRepr):
    name: str
    expected: Path | None
    actual: Path | None

    def actual_lines(self) -> list[str] | None:
        return self._lines(self.actual)

    def expected_lines(self) -> list[str] | None:
        return self._lines(self.expected)

    def _lines(self, path: Path | None) -> list[str] | None:
        if path:
            if path.is_file():
                return path.read_text().splitlines()
            if path.is_dir():
                return [f"{Icon.DIR} {self.name}"]
            if path.is_symlink():
                return [f"{Icon.SYMLINK} {self.name}"]
        return None

    @cached_property
    def kind(self) -> Kind:
        if self.expected and self.actual:
            if self.expected.is_file() and self.actual.is_file():
                return Kind.DIFF
            return Kind.TYPE_DIFF
        elif self.expected:
            return Kind.REMOVED
        else:
            return Kind.ADDED

    def toterminal(self, tw: TerminalWriter) -> None:
        differ = icdiff.ConsoleDiff(
            tabsize=2,
            cols=DIFF_WIDTH,
            highlight=True,
            truncate=True,
            line_numbers=True,
            show_all_spaces=True,
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

        symbol = Icon[self.kind]
        style = Style[self.kind]

        line_length = DIFF_WIDTH
        diff_header = f"╼ {symbol} {Style.NONE}{self.name} {style}╾"
        half_header, fill = divmod(line_length - len_no_ansi(diff_header), 2)

        actual_header = f"╴{Style.REMOVED}actual{style}╶"
        halt_left_header, remaining = divmod(half_header - len_no_ansi(actual_header), 2)
        left_header = halt_left_header * "─" + actual_header + (halt_left_header + remaining) * "─"

        expected_header = f"╴{Style.ADDED}expected{style}╶"
        halt_right_header, remaining = divmod(half_header - len_no_ansi(expected_header), 2)
        right_header = (
            halt_right_header * "─" + expected_header + (halt_right_header + remaining) * "─"
        )

        tw.line(
            "".join(
                (
                    style,
                    "╭",
                    left_header[1:],
                    diff_header,
                    right_header[:-1],
                    fill * "─",
                    "╮",
                )
            )
        )

        lines = differ.make_table(
            self.actual_lines() or [], self.expected_lines() or [], context=True
        )
        for line in lines:
            tw.line(color_off + line)

        tw.line(style + "╰" + (line_length - 1) * "─" + "╯")


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
            DiffRepr(
                prefix / name,
                actual=Path(self.left) / name,
                expected=Path(self.right) / name,
            ).toterminal(tw)
        for name in self.left_only:
            DiffRepr(
                prefix / name,
                actual=Path(self.left) / name,
                expected=None,
            ).toterminal(tw)
        for name in self.right_only:
            DiffRepr(
                prefix / name,
                actual=None,
                expected=Path(self.right) / name,
            ).toterminal(tw)
        for name, sub in self.subdirs.items():
            prefix = (prefix / name) if str(prefix) else Path(name)
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
