from dataclasses import dataclass, field
import os
from typing import AsyncGenerator, Literal
from contextlib import contextmanager
from enum import Enum

from autosh.md.stream import TextStream

HIGHLIGHT_COLOR_START = "35"
HIGHLIGHT_COLOR_END = "0"
ESC = "\x1b"


class Color(Enum):
    BLACK = 30, 40
    RED = 31, 41
    GREEN = 32, 42
    YELLOW = 33, 43
    BLUE = 34, 44
    MAGENTA = 35, 45
    CYAN = 36, 46
    WHITE = 37, 47

    BRIGHT_BLACK = 90, 100
    BRIGHT_RED = 91, 101
    BRIGHT_GREEN = 92, 102
    BRIGHT_YELLOW = 93, 103
    BRIGHT_BLUE = 94, 104
    BRIGHT_MAGENTA = 95, 105
    BRIGHT_CYAN = 96, 106
    BRIGHT_WHITE = 97, 107

    def __init__(self, foreground: int, background: int):
        self.foreground = foreground
        self.background = background


@dataclass
class State:
    is_bold: bool = False
    is_dim: bool = False
    is_italic: bool = False
    is_underline: bool = False
    is_strike: bool = False
    foreground_color: Color | None = None
    background_color: Color | None = None

    def emit(self, text: str):
        print(text, end="", flush=True)

    def _enter_scope(
        self,
        bold: bool | None = None,
        dim: bool | None = None,
        italic: bool | None = None,
        underline: bool | None = None,
        strike: bool | None = None,
        color: Color | None = None,
        bg: Color | None = None,
    ) -> "State":
        old_state = State(
            is_bold=self.is_bold,
            is_dim=self.is_dim,
            is_italic=self.is_italic,
            is_underline=self.is_underline,
            is_strike=self.is_strike,
            foreground_color=self.foreground_color,
            background_color=self.background_color,
        )
        if bold is not None:
            self.is_bold = bold
        if dim is not None:
            self.is_dim = dim
        if italic is not None:
            self.is_italic = italic
        if underline is not None:
            self.is_underline = underline
        if strike is not None:
            self.is_strike = strike
        if color is not None:
            self.foreground_color = color
        if bg is not None:
            self.background_color = bg
        self.__apply_all()
        return old_state

    def _exit_scope(self, old_state: "State"):
        self.is_bold = old_state.is_bold
        self.is_dim = old_state.is_dim
        self.is_italic = old_state.is_italic
        self.is_underline = old_state.is_underline
        self.is_strike = old_state.is_strike
        self.foreground_color = old_state.foreground_color
        self.background_color = old_state.background_color
        self.__apply_all()

    @contextmanager
    def style(
        self,
        bold: bool | None = None,
        dim: bool | None = None,
        italic: bool | None = None,
        underline: bool | None = None,
        strike: bool | None = None,
        color: Color | None = None,
        bg: Color | None = None,
    ):
        old_state = self._enter_scope(
            bold=bold,
            dim=dim,
            italic=italic,
            underline=underline,
            strike=strike,
            color=color,
            bg=bg,
        )
        yield
        self._exit_scope(old_state)

    def __apply_all(self):
        self.emit(f"{ESC}[0m")
        codes = []
        if self.is_bold:
            codes.append(1)
        if self.is_dim:
            codes.append(2)
        if self.is_italic:
            codes.append(3)
        if self.is_underline:
            codes.append(4)
        if self.is_strike:
            codes.append(9)
        if self.foreground_color:
            codes.append(self.foreground_color.foreground)
        if self.background_color:
            codes.append(self.background_color.background)

        codes = ";".join(map(str, codes))
        if len(codes) > 0:
            self.emit(f"{ESC}[{codes}m")


class StreamedMarkdownPrinter:
    def __init__(self, gen: AsyncGenerator[str, None]):
        self.stream = TextStream(gen)
        self.state = State()

    def emit(self, s: str):
        self.state.emit(s)

    def peek(self):
        return self.stream.peek()

    async def consume(self, n: int = 1):
        return await self.stream.consume(n)

    async def check(self, s: str, eof: bool | None = None) -> bool:
        return await self.stream.check(s, eof)

    async def parse_inline(self, consume_trailing_newline: bool = True):
        from autosh.md.inline_text import InlineTextPrinter

        itp = InlineTextPrinter(self)
        await itp.parse_inline(consume_trailing_newline)

    async def parse_heading(self):
        hashes = 0
        while True:
            c = await self.consume()
            if c == "#":
                hashes += 1
            else:
                break
        match hashes:
            case 1:
                with self.state.style(bold=True, bg=Color.MAGENTA):
                    with self.state.style(dim=True):
                        self.emit("#" * hashes + " ")
                    await self.parse_inline(consume_trailing_newline=False)
            case 2:
                with self.state.style(bold=True, underline=True, color=Color.MAGENTA):
                    with self.state.style(dim=True):
                        self.emit("#" * hashes + " ")
                    await self.parse_inline(consume_trailing_newline=False)
            case 3:
                with self.state.style(bold=True, color=Color.MAGENTA):
                    with self.state.style(dim=True):
                        self.emit("#" * hashes + " ")
                    await self.parse_inline(consume_trailing_newline=False)
            case 4:
                with self.state.style(bold=True, italic=True, color=Color.MAGENTA):
                    with self.state.style(dim=True):
                        self.emit("#" * hashes + " ")
                    await self.parse_inline(consume_trailing_newline=False)
            case _:
                with self.state.style(bold=True):
                    with self.state.style(dim=True):
                        self.emit("#" * hashes + " ")
                    await self.parse_inline(consume_trailing_newline=False)
        await self.consume()  # consume the newline
        self.emit("\n")

    async def parse_paragraph(self):
        while True:
            await self.parse_inline()
            if (
                self.peek() != "\n"
                and not await self.stream.non_paragraph_block_start()
            ):
                await self.consume()
                break
            else:
                break

    async def parse_multiline_code(self):
        with self.state.style(dim=True):
            self.emit("```")
            await self.consume(3)
            while not await self.check("\n```"):
                c = await self.consume()
                if c is None:
                    self.emit("\n")
                    return
                self.emit(c)
            self.emit("\n```\n")
            await self.consume(4)

    async def parse_list(self, ordered: bool):
        indents = [0]
        counter = [1]
        # first item
        if ordered:
            self.emit("1. ")
            await self.consume()
        else:
            self.emit("• ")
        await self.consume()
        await self.parse_inline()
        while True:
            indent = 0
            while self.peek() in [" ", "\t", "\n"]:
                if self.peek() in [" ", "\t"]:
                    indent += 1
                if self.peek() == "\n":
                    indent = 0
                await self.consume()
            if self.peek() is None:
                return
            if ordered and not await self.stream.ordered_list_label():
                return
            if not ordered and not await self.stream.unordered_list_label():
                return
            if not ordered:
                await self.consume()
            else:
                while self.peek() is not None and self.peek() != ".":
                    await self.consume()
                await self.consume()

            depth = None
            for i in range(len(indents) - 1):
                if indents[i] <= indent and indents[i + 1] > indent:
                    depth = i
                    break
            if depth is None and indents[-1] + 2 <= indent:
                # indent one more level
                indents.append(indent)
                depth = len(indents) - 1
                counter.append(1)
            elif depth is None:
                # same as last level
                depth = len(indents) - 1
                counter[depth] += 1
            else:
                # dedent
                indents = indents[: depth + 1]
                counter = counter[: depth + 1]
                counter[depth] += 1
            if not ordered:
                self.emit("  " * depth + "• ")
            else:
                self.emit("   " * depth + str(counter[depth]) + ". ")
            await self.parse_inline()

    async def parse_blockquote(self):
        while True:
            while self.peek() in [" ", "\t"]:
                await self.consume()
            if self.peek() != ">":
                break
            await self.consume()
            with self.state.style(bold=True, dim=True):
                self.emit("|")
            with self.state.style(dim=True):
                await self.parse_inline()

    async def parse_doc(self):
        await self.stream.init()
        start = True
        while True:
            # Remove leading spaces and empty lines
            indent = 0
            while self.peek() in [" ", "\t", "\n"]:
                if self.peek() in [" ", "\t"]:
                    indent += 1
                if self.peek() == "\n":
                    indent = 0
                await self.consume()
            if self.peek() is None:
                break
            if not start:
                self.emit("\n")
            start = False
            match c := self.peek():
                case None:
                    break
                # Heading
                case "#":
                    await self.parse_heading()
                # Code
                case "`" if await self.check("```"):
                    await self.parse_multiline_code()
                # Separator
                case _ if await self.check("---"):
                    await self.consume(3)
                    width = min(os.get_terminal_size().columns, 80)
                    with self.state.style(dim=True):
                        self.emit("─" * width)
                # Unordered list
                case _ if await self.stream.unordered_list_label():
                    await self.parse_list(False)
                # Ordered list
                case _ if await self.stream.ordered_list_label():
                    await self.parse_list(True)
                # Blockquote
                case ">":
                    await self.parse_blockquote()
                # Normal paragraph
                case _:
                    await self.parse_paragraph()
        self.emit("\x1b[0m")  # Reset all

    def __await__(self):
        return self.parse_doc().__await__()
