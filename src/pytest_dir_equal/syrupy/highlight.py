from __future__ import annotations

import os
import re

from typing import TYPE_CHECKING, Any, Iterator, TextIO

from _pytest.config.exceptions import UsageError
from syrupy.terminal import (
    _is_color_disabled,
)

try:
    import pygments.util

    from pygments import highlight
    from pygments.filter import simplefilter
    from pygments.filters import VisibleWhitespaceFilter
    from pygments.formatters.terminal256 import EscapeSequence, Terminal256Formatter
    from pygments.lexer import bygroups, inherit
    from pygments.lexers import guess_lexer, guess_lexer_for_filename
    from pygments.lexers.diff import DiffLexer, WDiffLexer
    from pygments.token import Generic, Other, Token, Whitespace
    from pygments.token import _TokenType as TokenType

    no_pygments = False
except ImportError:
    no_pygments = True


if TYPE_CHECKING:
    try:
        from pygments.lexer import (
            Lexer,
            LexerMeta,
        )
        from pygments.style import Style
    except Exception:
        Style = Lexer = LexerMeta = Any  # type: ignore

RE_ANSI = re.compile(r"\x1b\[\d+(;\d+){0,3}m")


def get_lexer(filename: str, source: str) -> Lexer | LexerMeta | None:
    if no_pygments or _is_color_disabled():
        return None

    lexer: Lexer | LexerMeta | None
    try:
        lexer = guess_lexer_for_filename(filename, source)
    except pygments.util.ClassNotFound:
        try:
            lexer = guess_lexer(source)
        except pygments.util.ClassNotFound:
            lexer = None
    return lexer


def highlight_file(filename: str, source: str) -> str:
    if lexer := get_lexer(filename, source):
        return _colorize(source, lexer)
    return source


def highlight_diff(diff: Iterator[str]) -> Iterator[str]:
    if no_pygments or _is_color_disabled():
        return diff

    lines = (RE_ANSI.sub("", line) if line.startswith(("+", "-")) else line for line in diff)
    if raw := "".join(lines):
        lexer = UWDiffLexer()
        # lexer.add_filter(VisibleWhitespaceFilter(spaces=True, newlines=True, wstokentype=False))
        lexer.add_filter(strip_wdiff())
        return iter(_colorize(raw, lexer).splitlines(keepends=True))
    return diff


@simplefilter
def strip_wdiff(self, lexer, stream, options):
    for ttype, value in stream:
        if ttype.parent in (SpanInserted, SpanDeleted):
            value = ""
        yield ttype, value


UWDiff = Token.UWDiff
LineInserted = UWDiff.LineInserted
LineDeleted = UWDiff.LineDeleted
SpanInserted = UWDiff.SpanInserted
SpanDeleted = UWDiff.SpanDeleted

DiffTokens = (
    LineInserted,
    LineDeleted,
    SpanInserted,
    SpanInserted.Open,
    SpanInserted.Close,
    SpanDeleted,
    SpanDeleted.Open,
    SpanDeleted.Close,
)

OpenTokens = (
    LineInserted,
    LineDeleted,
    SpanInserted.Open,
    SpanDeleted.Open,
)

CloseTokens = (
    SpanInserted.Close,
    SpanDeleted.Close,
)


class UWDiffLexer(DiffLexer):
    """
    Lexer for unified or context-style diffs or patches.
    """

    ins_op = WDiffLexer.ins_op
    ins_cl = WDiffLexer.ins_cl
    del_op = WDiffLexer.del_op
    del_cl = WDiffLexer.del_cl
    normal = r"[^{}[\]+-]+"  # for performance
    tokens = {
        "root": [
            (r"(< |- )", LineDeleted, "deleted_line"),
            (r"(> |\+ )", LineInserted, "inserted_line"),
            inherit,
        ],
        "inserted_line": [
            (rf"({ins_op})(.+?)({ins_cl})", bygroups(SpanInserted.Open, Other, SpanInserted.Close)),
            (r"((?!\{(?=\+)|\+(?=\})|(?<=\{)\+|(?<=\+)\}|\n).)+", Generic.Other),
            (r"\n", Other, "#pop"),
        ],
        "deleted_line": [
            (rf"({del_op})(.+?)({del_cl})", bygroups(SpanDeleted.Open, Other, SpanDeleted.Close)),
            (r"[^[\]+\n]+", Generic.Other),
            (r"\n", Other, "#pop"),
        ],
    }


def _style() -> type[Style]:
    from pygments.styles import get_style_by_name
    from pygments.token import Generic
    from pygments.util import ClassNotFound

    try:
        style = get_style_by_name(os.getenv("PYTEST_THEME", "default"))
    except ClassNotFound:
        style = get_style_by_name("default")

    class SyrupyStyle(style):
        INSERTED = "d7ffff"
        INSERTED_DARKER = "005f5f"
        DELETED = "ffd7ff"
        DELETED_DARKER = "870087"
        styles = {
            **style.styles,
            Generic.Inserted: f"bg:#{INSERTED} #{INSERTED_DARKER}",
            Generic.Deleted: f"bg:#{DELETED} #{DELETED_DARKER}",
            LineInserted: f"bg:#{INSERTED} #{INSERTED_DARKER}",
            LineDeleted: f"bg:#{DELETED} #{DELETED_DARKER}",
        }
        diff_bgs = {
            LineInserted: f"{INSERTED}",
            LineDeleted: f"{DELETED}",
            SpanInserted.Open: f"{INSERTED_DARKER}",
            SpanDeleted.Open: f"{DELETED_DARKER}",
        }

    return SyrupyStyle


ColorSpec = tuple[str, str]
"""colors specs in form (open, end)"""


class SyrupyFormatter(Terminal256Formatter):
    diff_style_string: dict[str, ColorSpec]

    diff_bg: dict[str, ColorSpec]

    def _setup_styles(self):
        self.diff_style_string = {}
        for ttype, ndef in self.style:
            escape = EscapeSequence()
            diff_escape = EscapeSequence()
            # get foreground from ansicolor if set
            if ndef["ansicolor"]:
                diff_escape.fg = escape.fg = self._color_index(ndef["ansicolor"])
            elif ndef["color"]:
                diff_escape.fg = escape.fg = self._color_index(ndef["color"])
            if ndef["bgansicolor"]:
                escape.bg = self._color_index(ndef["bgansicolor"])
            elif ndef["bgcolor"]:
                escape.bg = self._color_index(ndef["bgcolor"])
            if self.usebold and ndef["bold"]:
                diff_escape.bold = escape.bold = True
            if self.useunderline and ndef["underline"]:
                diff_escape.underline = escape.underline = True
            if self.useitalic and ndef["italic"]:
                diff_escape.italic = escape.italic = True
            self.style_string[str(ttype)] = (escape.color_string(), escape.reset_string())
            self.diff_style_string[str(ttype)] = (escape.color_string(), escape.reset_string())

        self.diff_bg = {}
        for ttype, color in self.style.diff_bgs.items():
            escape = EscapeSequence()
            escape.bg = self._color_index(color)
            self.diff_bg[str(ttype)] = (escape.color_string(), escape.reset_string())

    def format_unencoded(self, tokensource: Iterator[tuple[TokenType, str]], outfile: TextIO):
        if self.linenos:
            self._write_lineno(outfile)

        in_diff = False
        bgs: list[ColorSpec] = []  # Backgrounds stack
        bg: ColorSpec | None = None  # current background
        for ttype, value in tokensource:
            if in_diff and ttype is Other and value == "\n":
                in_diff = False
                bgs = []
                bg = None
            elif ttype in OpenTokens:
                in_diff = True
                if diff_bg := self.diff_bg.get(str(ttype)):
                    bgs.append(diff_bg)
                    bg = diff_bg
            elif ttype in CloseTokens and bg:
                outfile.write(bg[1])
                bgs.pop()
                try:
                    bg = bgs[-1]
                except IndexError:
                    bg = None

            not_found = True

            while ttype and not_found:
                style = self.diff_style_string if in_diff else self.style_string
                try:
                    on, off = style[str(ttype)]
                    if bg:
                        on = on + bg[0]
                        off = off + bg[1]
                except KeyError:
                    ttype = ttype.parent
                else:
                    # Like TerminalFormatter, add "reset colors" escape sequence
                    # on newline.
                    spl = value.split("\n")
                    for line in spl[:-1]:
                        if line:
                            end = "" if ttype in OpenTokens else off
                            outfile.write(on + line + end)
                        if self.linenos:
                            self._write_lineno(outfile)
                        else:
                            outfile.write("\n")

                    if spl[-1]:
                        end = "" if ttype in OpenTokens else off
                        outfile.write(on + spl[-1] + end)

                    not_found = False

            if not_found:
                outfile.write(value)

        if self.linenos:
            outfile.write("\n")


def _colorize(source: str, lexer: Lexer | LexerMeta) -> str:
    """Highlight the given source code if we have markup support."""
    if no_pygments or _is_color_disabled():
        return source

    try:
        highlighted = highlight(
            source,
            lexer,
            SyrupyFormatter(style=_style()),
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
