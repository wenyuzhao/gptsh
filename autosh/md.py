import os
from typing import AsyncGenerator, Literal

import rich
import rich.panel

HIGHLIGHT_COLOR_START = "35"
HIGHLIGHT_COLOR_END = "0"


class MarkdowmPrinter:
    def __init__(self, stream: AsyncGenerator[str, None]):
        async def char_stream(stream: AsyncGenerator[str, None]):
            async for chunk in stream:
                for char in chunk:
                    yield char

        self.stream = char_stream(stream)
        self.__buf: str = ""
        self.__eof = False

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

    async def check(self, s: str):
        if len(s) == 0:
            return True
        if self.__eof:
            return False
        await self.__ensure_length(len(s))
        return self.__buf[0 : len(s)] == s

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

    def print(self, s: str):
        print(s, end="", flush=True)

    async def parse_single_line_text(
        self,
        outer_is_italic: bool = False,
        outer_is_bold: bool = False,
        outer_is_dim: bool = False,
    ):
        styles: list[Literal["code", "bold", "italic", "strike"]] = []

        def find(s: Literal["code", "bold", "italic", "strike"]):
            for i in range(len(styles) - 1, -1, -1):
                if styles[i] == s:
                    return i
            return None

        def find_italic_first():
            for i in range(len(styles) - 1, -1, -1):
                if styles[i] == "bold":
                    return False
                if styles[i] == "italic":
                    return True
            return False

        # Remove leading spaces
        while self.peek() in [" ", "\t"]:
            await self.next()

        while True:
            not_code = find("code") is None
            c = self.peek()
            if c == "\n" or c is None:
                await self.next()
                self.print("\x1b[0m\n")  # Reset all and newline
                return
            match c:
                case "`":
                    await self.next()
                    if (i := find("code")) is not None:
                        if not outer_is_dim:
                            self.print("\x1b[22m")
                            if find("bold") is not None or outer_is_bold:
                                self.print("\x1b[1m")
                        styles = styles[:i]
                    else:
                        self.print("\x1b[2m")
                        styles.append("code")
                # Bold
                case "*" if (
                    not_code and await self.check("**") and not find_italic_first()
                ):
                    await self.next()
                    await self.next()
                    # print(">", styles, find("bold"))
                    if (i := find("bold")) is not None:
                        if not outer_is_bold:
                            self.print("\x1b[22m")
                        styles = styles[:i]
                    else:
                        self.print("\x1b[1m")
                        styles.append("bold")
                case "_" if (
                    not_code and await self.check("__") and not find_italic_first()
                ):
                    await self.next()
                    await self.next()
                    if (i := find("bold")) is not None:
                        if not outer_is_bold:
                            self.print("\x1b[22m")
                        styles = styles[:i]
                    else:
                        self.print("\x1b[1m")
                        styles.append("bold")
                # Italic
                case "*" | "_" if not_code:
                    await self.next()
                    if (i := find("italic")) is not None:
                        if not outer_is_italic:
                            self.print("\x1b[23m")
                        styles = styles[:i]
                        # print(styles, await self.check("**"))
                    else:
                        self.print("\x1b[3m")
                        styles.append("italic")
                # Strike through
                case "~" if not_code and await self.check("~~"):
                    await self.next()
                    await self.next()
                    if (i := find("strike")) is not None:
                        self.print("\x1b[29m")
                        styles = styles[:i]
                    else:
                        self.print("\x1b[9m")
                        styles.append("strike")
                case _:
                    self.print(c)
                    await self.next()

    async def parse_heading(self):
        hashes = 0
        while True:
            c = await self.next()
            if c == "#":
                hashes += 1
            else:
                break
        # Start control
        match hashes:
            case 1:
                self.print("\x1b[45;1;2m")  # Magenta background, bold, dim
                self.print("#" * hashes)
                self.print(" \x1b[22;1m")  # Reset dim
                await self.parse_single_line_text(outer_is_bold=True)
            case 2:
                self.print("\x1b[35;1;2;4m")  # Magenta foreground, bold, dim, underline
                self.print("#" * hashes)
                self.print(" \x1b[22m\x1b[1m")  # Reset dim
                await self.parse_single_line_text(outer_is_bold=True)
            case 3:
                self.print("\x1b[35;1;2m")  # Magenta foreground, bold, dim
                self.print("#" * hashes)
                self.print(" \x1b[22m\x1b[1m")  # Reset dim
                await self.parse_single_line_text(outer_is_bold=True)
            case 4:
                self.print("\x1b[35;2;3m")  # Magenta foreground, dim, italic
                self.print("#" * hashes)
                self.print(" \x1b[22m")  # Reset dim
                await self.parse_single_line_text(outer_is_italic=True)
            case _:
                self.print("\x1b[2m")  # dim
                self.print("#" * hashes)
                self.print(" \x1b[22m")  # Reset dim
                await self.parse_single_line_text()
        # Stream title

    async def parse_paragraph(self):
        while True:
            await self.parse_single_line_text()
            if self.peek() != "\n":
                await self.next()
                break
            else:
                break

    async def parse_multiline_code(self):
        # dim
        self.print("\x1b[2m")
        self.print("```")
        await self.next()
        await self.next()
        await self.next()
        while not await self.check("\n```"):
            c = await self.next()
            if c is None:
                return
            self.print(c)
        self.print("\n```\n")
        await self.next()
        await self.next()
        await self.next()
        await self.next()

    async def parse_list(self, ordered: bool):
        indents = [0]
        counter = [1]
        # first item
        if ordered:
            self.print("1. ")
            await self.next()
        else:
            self.print("• ")
        await self.next()
        await self.parse_single_line_text()
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
                self.print("  " * depth + "• ")
            else:
                self.print("   " * depth + str(counter[depth]) + ". ")
            await self.parse_single_line_text()

    async def parse_blockquote(self):
        while True:
            while self.peek() in [" ", "\t"]:
                await self.next()
            if self.peek() != ">":
                break
            await self.next()
            self.print("\x1b[1;2m|\x1b[22;2m ")
            await self.parse_single_line_text(outer_is_dim=True)

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
                self.print("\n")
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
                    self.print("\x1b[2m" + "-" * width + "\x1b[22m\n")
                # Unordered list
                case "-" | "+" | "*":
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
            self.print("\x1b[0m\x1b[0m\x1b[0m")  # Reset all
        self.print("\x1b[0m")  # Reset all

    def __await__(self):
        return self.parse_doc().__await__()


async def stream_md(stream: AsyncGenerator[str, None]):
    mp = MarkdowmPrinter(stream)
    await mp.parse_doc()
