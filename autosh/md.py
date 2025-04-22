from dataclasses import dataclass, field
import os
from typing import AsyncGenerator, Literal
from contextlib import contextmanager
from enum import Enum

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


@dataclass
class Keyword:
    token: str

    def is_bold(self) -> bool:
        return self.token[0] in ["*", "_"] and len(self.token) == 2

    def is_italic(self) -> bool:
        return self.token[0] in ["*", "_"] and len(self.token) == 1

    def is_bold_and_italic(self) -> bool:
        return self.token[0] in ["*", "_"] and len(self.token) > 2

    def is_bold_or_italic(self) -> bool:
        return self.token[0] in ["*", "_"]


@dataclass
class InlineScope:
    state: State

    stack: list[tuple[Keyword, State]] = field(default_factory=list)

    @property
    def last(self) -> str | None:
        return self.stack[-1][0].token if len(self.stack) > 0 else None

    @property
    def strike(self) -> bool:
        return self.last == "~~"

    @property
    def code(self) -> bool:
        return self.last == "`"

    def enter(self, kind: Keyword):
        match kind:
            case "`":
                state = self.state._enter_scope(dim=True)
            case "~~":
                state = self.state._enter_scope(strike=True)
            case _ if kind.is_bold():
                state = self.state._enter_scope(bold=True)
            case _ if kind.is_italic():
                state = self.state._enter_scope(italic=True)
            case _ if kind.is_bold_and_italic():
                state = self.state._enter_scope(bold=True, italic=True)
            case _:
                state = self.state._enter_scope()
        self.stack.append((kind, state))

    def exit(self):
        t = self.stack.pop()
        state = t[1]
        self.state._exit_scope(state)


class InvalidState(Exception):
    def __init__(self, token: str):
        super().__init__(token)
        self.token = token


class StreamedMarkdownPrinter:
    def __init__(self, stream: AsyncGenerator[str, None]):
        async def char_stream(stream: AsyncGenerator[str, None]):
            async for chunk in stream:
                for char in chunk:
                    yield char

        self.stream = char_stream(stream)
        self.__buf: str = ""
        self.__eof = False
        self.state = State()

    def peek(self):
        c = self.__buf[0] if len(self.__buf) > 0 else None
        return c

    async def __ensure_length(self, n: int):
        while (not self.__eof) and len(self.__buf) < n:
            try:
                self.__buf += await self.stream.__anext__()
            except StopAsyncIteration:
                self.__eof = True

    async def __check_unordered_list_label(self) -> bool:
        if self.__eof:
            return False
        await self.__ensure_length(2)
        buf = self.__buf
        if len(buf) < 2:
            return False
        if buf[0] in ["-", "+", "*"] and buf[1] == " ":
            return True
        return False

    async def __check_ordered_list_label(self) -> bool:
        if self.__eof:
            return False
        await self.__ensure_length(5)
        buf = self.__buf
        # \d+\.
        if len(buf) == 0:
            return False
        if not buf[0].isnumeric():
            return False
        has_dot = False
        for i in range(1, 5):
            if i >= len(buf):
                return False
            c = buf[i]
            if c == ".":
                if has_dot:
                    return False
                has_dot = True
                continue
            if c == " ":
                if has_dot:
                    return True
                return False
            if c.isnumeric():
                continue
        return False

    async def check(self, s: str, eof: bool | None = None) -> bool:
        if len(s) == 0:
            return True
        await self.__ensure_length(len(s) + 1)
        if len(self.__buf) < len(s):
            return False
        matched = self.__buf[0 : len(s)] == s
        if matched:
            if eof is not None:
                if eof:
                    # return false if there is more data
                    if len(self.__buf) > len(s):
                        return False
                else:
                    # return false if there is no more data
                    if len(self.__buf) == len(s):
                        return False
        return matched

    async def check_non_paragraph_block_start(self):
        await self.__ensure_length(3)
        buf = self.__buf[:3] if len(self.__buf) >= 3 else self.__buf
        if buf.startswith("```"):
            return True
        if buf.startswith("---"):
            return True
        if buf.startswith("> "):
            return True
        if await self.__check_ordered_list_label():
            return True
        if await self.__check_unordered_list_label():
            return True
        return False

    async def next(self):
        c = self.__buf[0] if len(self.__buf) > 0 else None
        self.__buf = self.__buf[1:] if len(self.__buf) > 0 else ""
        if c is None:
            return None
        if not self.__eof:
            try:
                self.__buf += await self.stream.__anext__()
            except StopAsyncIteration:
                self.__eof = True
        return c

    async def consume(self, n: int = 1):
        while n > 0:
            c = await self.next()
            if c is None:
                break
            n -= 1

    def emit(self, s: str):
        self.state.emit(s)

    async def parse_inline_code(self):
        self.emit("`")
        # Parse until another "`" or a newline, or EOF
        while not await self.check("`"):
            c = await self.next()
            if c is None or c == "\n":
                return
            self.emit(c)
            if c == "\\":
                c = await self.next()
                if c is None or c == "\n":
                    return
                self.emit(c)
        self.emit("`")
        await self.next()

    async def get_next_token(self) -> str | Keyword | None:
        c = self.peek()
        if c is None or c == "\n":
            return None
        if c == "`":
            await self.next()
            return Keyword("`")
        if c == "*":
            s = ""
            while self.peek() == "*":
                s += c
                await self.next()
            return Keyword(s)
        if c == "_":
            s = ""
            while self.peek() == "_":
                s += c
                await self.next()
            return Keyword(s)
        if c == "~" and await self.check("~~"):
            s = ""
            while self.peek() == "~":
                s += c
                await self.next()
            return Keyword(s)
        if c == " " or c == "\t":
            s = ""
            while self.peek() == " " or self.peek() == "\t":
                s += c
                await self.next()
            return s
        s = ""
        while c is not None and c != "\n" and c not in ["`", "*", "_", "~", " "]:
            s += c
            await self.next()
            c = self.peek()
            if c == "\\":
                await self.next()
                s += c
                c = self.peek()
                if c is None or c == "\n":
                    return None if len(s) == 0 else s
                s += c
                await self.next()
        if len(s) == 0:
            return None
        return s

    async def _parse_inline(self, consume_trailing_newline: bool = True):
        last_is_space_or_start = False
        start = True
        scope = InlineScope(self.state)

        while True:
            t = await self.get_next_token()
            curr_is_space = False
            start = False

            if t is None:
                if consume_trailing_newline:
                    await self.consume()
                    self.emit("\n")
                return
            elif isinstance(t, str):
                # Space or normal text
                if t[0] == " ":
                    curr_is_space = True
                    self.emit(" ")
                else:
                    self.emit(t)
            elif t.token == "`":
                # Inline code
                scope.enter(t)
                with self.state.style(dim=True):
                    await self.parse_inline_code()
                scope.exit()
            elif t.token == "~~":
                # Strike through
                if not scope.strike:
                    scope.enter(t)
                    self.emit("~~")
                else:
                    self.emit("~~")
                    scope.exit()
            elif (
                t.is_bold_or_italic()
                and last_is_space_or_start
                and scope.last != t.token
            ):
                # Start bold or italics
                scope.enter(t)
                self.emit(t.token)
            elif (
                t.is_bold_or_italic()
                and self.peek() in [" ", "\t", None]
                and scope.last == t.token
            ):
                # End bold or italics
                self.emit(t.token)
                scope.exit()
            else:
                print(
                    f"Invalid token: {t.token}",
                    self.peek(),
                    scope.last,
                    t.is_bold_or_italic(),
                    last_is_space_or_start,
                )
                raise InvalidState(t.token)

            last_is_space_or_start = curr_is_space or start

    async def parse_heading(self):
        hashes = 0
        while True:
            c = await self.next()
            if c == "#":
                hashes += 1
            else:
                break
        match hashes:
            case 1:
                with self.state.style(bold=True, bg=Color.MAGENTA):
                    with self.state.style(dim=True):
                        self.emit("#" * hashes + " ")
                    await self._parse_inline(consume_trailing_newline=False)
            case 2:
                with self.state.style(bold=True, underline=True, color=Color.MAGENTA):
                    with self.state.style(dim=True):
                        self.emit("#" * hashes + " ")
                    await self._parse_inline(consume_trailing_newline=False)
            case 3:
                with self.state.style(bold=True, color=Color.MAGENTA):
                    with self.state.style(dim=True):
                        self.emit("#" * hashes + " ")
                    await self._parse_inline(consume_trailing_newline=False)
            case 4:
                with self.state.style(bold=True, italic=True, color=Color.MAGENTA):
                    with self.state.style(dim=True):
                        self.emit("#" * hashes + " ")
                    await self._parse_inline(consume_trailing_newline=False)
            case _:
                with self.state.style(bold=True):
                    with self.state.style(dim=True):
                        self.emit("#" * hashes + " ")
                    await self._parse_inline(consume_trailing_newline=False)
        await self.consume()  # consume the newline
        self.emit("\n")

    async def parse_paragraph(self):
        while True:
            await self._parse_inline()
            if self.peek() != "\n" and not await self.check_non_paragraph_block_start():
                await self.next()
                break
            else:
                break

    async def parse_multiline_code(self):
        with self.state.style(dim=True):
            self.emit("```")
            await self.next()
            await self.next()
            await self.next()
            while not await self.check("\n```"):
                c = await self.next()
                if c is None:
                    self.emit("\n")
                    return
                self.emit(c)
            self.emit("\n```\n")
            await self.next()
            await self.next()
            await self.next()
            await self.next()

    async def parse_list(self, ordered: bool):
        indents = [0]
        counter = [1]
        # first item
        if ordered:
            self.emit("1. ")
            await self.next()
        else:
            self.emit("• ")
        await self.next()
        await self._parse_inline()
        while True:
            indent = 0
            while self.peek() in [" ", "\t", "\n"]:
                if self.peek() in [" ", "\t"]:
                    indent += 1
                if self.peek() == "\n":
                    indent = 0
                await self.next()
            if self.peek() is None:
                return
            if ordered and not await self.__check_ordered_list_label():
                return
            if not ordered and not await self.__check_unordered_list_label():
                return
            if not ordered:
                await self.next()
            else:
                while self.peek() is not None and self.peek() != ".":
                    await self.next()
                await self.next()

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
            await self._parse_inline()

    async def parse_blockquote(self):
        while True:
            while self.peek() in [" ", "\t"]:
                await self.next()
            if self.peek() != ">":
                break
            await self.next()
            with self.state.style(bold=True, dim=True):
                self.emit("|")
            with self.state.style(dim=True):
                await self._parse_inline()

    async def parse_doc(self):
        self.__buf = await self.stream.__anext__()
        start = True
        while True:
            # Remove leading spaces and empty lines
            indent = 0
            while self.peek() in [" ", "\t", "\n"]:
                if self.peek() in [" ", "\t"]:
                    indent += 1
                if self.peek() == "\n":
                    indent = 0
                await self.next()
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
                    await self.next()
                    await self.next()
                    await self.next()
                    width = min(os.get_terminal_size().columns, 80)
                    with self.state.style(dim=True):
                        self.emit("─" * width)
                # Unordered list
                case _ if await self.__check_unordered_list_label():
                    await self.parse_list(False)
                # Ordered list
                case _ if await self.__check_ordered_list_label():
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


async def stream_md(stream: AsyncGenerator[str, None]):
    mp = StreamedMarkdownPrinter(stream)
    await mp.parse_doc()
