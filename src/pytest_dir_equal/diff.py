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
    TYPE_CHECKING,
    Any,
    Iterator,
    Protocol,
    TypeVar,
    cast,
)

from _pytest.config.exceptions import UsageError
from pygments.styles import get_style_by_name
from pygments.token import Generic
from pygments.util import ClassNotFound

if TYPE_CHECKING:
    try:
        from pygments.lexer import (
            Lexer,
            LexerMeta,
        )
        from pygments.style import Style
    except Exception:
        Style = Lexer = LexerMeta = Any  # type: ignore


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


# def wdiff(a: str, b: str, fromfile='', tofile='', n=3):
#     matcher = difflib.SequenceMatcher(None, a, b)
#     def process_tag(tag, i1, i2, j1, j2):
#         if tag == 'replace':
#             return f"[-{matcher.a[i1:i2]}-]{{+{matcher.b[j1:j2]}-}}"
#         if tag == 'delete':
#             return f"[-{matcher.a[i1:i2]}-]"
#         if tag == 'equal':
#             return matcher.a[i1:i2]
#         if tag == 'insert':
#             return f"{{+{matcher.b[j1:j2]}-}}"
#         assert False, "Unknown tag %r"%tag
#     return ''.join(process_tag(*t) for t in matcher.get_opcodes())


def wdiff(a: str, b: str, fromfile="", tofile="", n=3, lineterm="\n"):
    started = False
    for group in difflib.SequenceMatcher(None, a, b).get_grouped_opcodes(n):
        if not started:
            started = True
            # fromdate = '\t{}'.format(fromfiledate) if fromfiledate else ''
            # todate = '\t{}'.format(tofiledate) if tofiledate else ''
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
            if tag in {"replace", "delete"}:
                for line in a[i1:i2]:
                    yield "-" + line
            if tag in {"replace", "insert"}:
                for line in b[j1:j2]:
                    yield "+" + line
    matcher = difflib.SequenceMatcher(None, a, b)

    def process_tag(tag, i1, i2, j1, j2):
        if tag == "replace":
            return f"[-{matcher.a[i1:i2]}-]{{+{matcher.b[j1:j2]}-}}"
        if tag == "delete":
            return f"[-{matcher.a[i1:i2]}-]"
        if tag == "equal":
            return matcher.a[i1:i2]
        if tag == "insert":
            return f"{{+{matcher.b[j1:j2]}-}}"
        assert False, "Unknown tag %r" % tag

    return "".join(process_tag(*t) for t in matcher.get_opcodes())

    for group in SequenceMatcher(None, a, b).get_grouped_opcodes(n):
        if not started:
            started = True
            fromdate = f"\t{fromfiledate}" if fromfiledate else ""
            todate = f"\t{tofiledate}" if tofiledate else ""
            yield f"--- {fromfile}{fromdate}{lineterm}"
            yield f"+++ {tofile}{todate}{lineterm}"

        first, last = group[0], group[-1]
        file1_range = _format_range_unified(first[1], last[2])
        file2_range = _format_range_unified(first[3], last[4])
        yield f"@@ -{file1_range} +{file2_range} @@{lineterm}"

        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                for line in a[i1:i2]:
                    yield " " + line
                continue
            if tag in {"replace", "delete"}:
                for line in a[i1:i2]:
                    yield "-" + line
            if tag in {"replace", "insert"}:
                for line in b[j1:j2]:
                    yield "+" + line


# def unified_diff(a, b, fromfile='', tofile='', fromfiledate='',
#                  tofiledate='', n=3, lineterm='\n'):

#     difflib._check_types(a, b, fromfile, tofile, fromfiledate, tofiledate, lineterm)
#     started = False
#     for group in SequenceMatcher(None,a,b).get_grouped_opcodes(n):
#         if not started:
#             started = True
#             fromdate = '\t{}'.format(fromfiledate) if fromfiledate else ''
#             todate = '\t{}'.format(tofiledate) if tofiledate else ''
#             yield '--- {}{}{}'.format(fromfile, fromdate, lineterm)
#             yield '+++ {}{}{}'.format(tofile, todate, lineterm)

#         first, last = group[0], group[-1]
#         file1_range = _format_range_unified(first[1], last[2])
#         file2_range = _format_range_unified(first[3], last[4])
#         yield '@@ -{} +{} @@{}'.format(file1_range, file2_range, lineterm)

#         for tag, i1, i2, j1, j2 in group:
#             if tag == 'equal':
#                 for line in a[i1:i2]:
#                     yield ' ' + line
#                 continue
#             if tag in {'replace', 'delete'}:
#                 for line in a[i1:i2]:
#                     yield '-' + line
#             if tag in {'replace', 'insert'}:
#                 for line in b[j1:j2]:
#                     yield '+' + line


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
        source = file.read_text()

        if _is_color_disabled():
            return source
        try:
            import pygments.util

            from pygments.lexers import (
                guess_lexer,
                guess_lexer_for_filename,
            )
        except ImportError:
            return source

        lexer: Lexer | LexerMeta
        try:
            lexer = guess_lexer_for_filename(self.name, source)
        except pygments.util.ClassNotFound:
            try:
                lexer = guess_lexer(source)
            except pygments.util.ClassNotFound:
                return source

        return _colorize(source, lexer)

    def _colorize(self, diff: Iterator[str]) -> Iterator[str]:
        if _is_color_disabled():
            return diff

        # for line in diff:
        #     # print(f"{line=}")
        #     if line.startswith("+"):
        #         print(reset(_stylize(line, _bg(195))))
        #     elif line.startswith("-"):
        #         print(reset(_stylize(line, _bg(225))))
        #     elif line.startswith("@"):
        #         print(reset(warning_style(line)))
        #     else:
        #         print(reset(context_style(line)))

        try:
            from pygments.lexers.diff import DiffLexer
        except ImportError:
            return diff

        lines = (RE_ANSI.sub("", line) if line.startswith(("+", "-")) else line for line in diff)
        # for line in diff:
        #     ):
        #         print(line, )
        if raw := "".join(lines):
            return iter(_colorize(raw, DiffLexer()).splitlines(keepends=True))
        return diff

    # def _colorize(self, diff: Iterator[str]) -> Iterator[str]:
    #     if _is_color_disabled():
    #         return diff
    #     try:
    #         from pygments.lexers.diff import DiffLexer
    #     except ImportError:
    #         return diff

    #     if raw := "".join(diff):
    #         return iter(_colorize(raw, DiffLexer()).splitlines(keepends=True))
    #     return diff

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

        # yield from reporter.diff(actual, expected)

        print(wdiff(snapshot, received))

        diff = self._colorize(
            difflib.unified_diff(
                snapshot.splitlines(keepends=True),
                received.splitlines(keepends=True),
                f"<snapshot>/{self.name}",
                f"<received>/{self.name}",
            )
        )

        for line in diff:
            yield reset(line.rstrip("\n"))


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


def _colorize(source: str, lexer: Lexer | LexerMeta) -> str:
    """Highlight the given source code if we have markup support."""
    if _is_color_disabled():
        return source
    try:
        import pygments.util

        from pygments import highlight
        from pygments.formatters.terminal256 import Terminal256Formatter
    except ImportError:
        return source

    try:
        highlighted = highlight(
            source,
            lexer,
            Terminal256Formatter(style=_style()),
        )
    except pygments.util.ClassNotFound:
        raise UsageError(
            "PYTEST_THEME environment variable had an invalid value: '{}'. "
            "Only valid pygment styles are allowed.".format(os.getenv("PYTEST_THEME"))
        )
    except pygments.util.OptionError:
        raise UsageError(
            "PYTEST_THEME_MODE environment variable had an invalid value: '{}'. "
            "The only allowed values are 'dark' and 'light'.".format(os.getenv("PYTEST_THEME_MODE"))
        )
    return highlighted


class DirDiff(filecmp.dircmp[Any]):
    ignore: list[str]
    hide: list[str]

    EXCLUDED: list[str] = [  # Always ignored files (internals)
        ".gitkeep",
    ]

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}({self.left_only=}, {self.right_only=}, {self.common_funny=}, "
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

    def diff_lines(self, ctx: Ctx, prefix: Path | None = None) -> Iterator[str]:
        prefix = prefix or Path("")
        for name in self.diff_files:
            diff = FileDiff(
                snapshot=Path(self.right) / name,
                received=Path(self.left) / name,
            )
            yield from diff.diff_lines()
        for name in self.left_only:
            yield ctx.reset(
                ctx.received_style(
                    f"+++ added: <received>/{ctx.received_diff_style(prefix / name)}"
                )
            )
            yield ctx.reset(ctx.snapshot_style("--- N/A"))
        for name in self.right_only:
            yield ctx.reset(ctx.received_style("+++ N/A"))
            yield ctx.reset(
                ctx.snapshot_style(
                    f"--- missing: <snapshot>/{ctx.snapshot_diff_style(prefix / name)}"
                )
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
