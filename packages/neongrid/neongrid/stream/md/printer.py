import os
from typing import AsyncIterator, Literal
import unicodedata

from neongrid.style import STYLE, StyleScope
from .stream import TextStream


class StreamedMarkdownPrinter:
    def __init__(self, gen: AsyncIterator[str]):
        self.stream = TextStream(gen)
        self.state = StyleScope()

    def emit(self, s: str):
        self.state.emit(s)

    def peek(self):
        return self.stream.peek()

    async def consume(self, n: int = 1):
        return await self.stream.consume(n)

    async def check(self, s: str, eof: bool | None = None) -> bool:
        return await self.stream.check(s, eof)

    async def parse_inline(self, consume_trailing_newline: bool = True):
        from .inline_text import InlineTextPrinter

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
                with self.state.style(bold=True, bg=STYLE.highlight):
                    self.emit(" ")
                    await self.parse_inline(consume_trailing_newline=False)
                    self.emit(" ")
            case 2:
                with self.state.style(bold=True, underline=True, color=STYLE.highlight):
                    await self.parse_inline(consume_trailing_newline=False)
            case 3:
                with self.state.style(bold=True, italic=True, color=STYLE.highlight):
                    await self.parse_inline(consume_trailing_newline=False)
            case 4:
                with self.state.style(bold=True, color=STYLE.highlight):
                    await self.parse_inline(consume_trailing_newline=False)
            case _:
                with self.state.style(bold=True):
                    await self.parse_inline(consume_trailing_newline=False)
        await self.consume()  # consume the newline
        self.emit("\n")

    async def parse_paragraph(self):
        while True:
            await self.parse_inline()
            if (
                self.peek() is not None
                and self.peek() != "\n"
                and not await self.stream.non_paragraph_block_start()
            ):
                continue
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
            self.emit("1.")
            await self.consume()
        else:
            self.emit("•")
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
            if await self.stream.ordered_list_label():
                ordered = True
                # return
            elif await self.stream.unordered_list_label():
                ordered = False
            else:
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
                self.emit("   " * depth + "•")
            else:
                self.emit("   " * depth + str(counter[depth]) + ".")
            await self.parse_inline()

    async def parse_blockquote(self):
        from .inline_text import InlineTextPrinter

        while True:
            while self.peek() in [" ", "\t"]:
                await self.consume()
            if self.peek() != ">":
                break
            await self.consume()
            with self.state.style(bold=True, dim=True):
                self.emit(">")
            with self.state.style(dim=True):
                itp = InlineTextPrinter(self)
                await itp.parse_inline_unformatted()
            if self.peek() == "\n":
                self.emit("\n")
                await self.consume()

    async def parse_table(self):
        def str_size(s: str) -> int:
            size = 0
            for c in s:
                match unicodedata.east_asian_width(c):
                    case "F" | "W":
                        size += 2
                    case _:
                        size += 1
            return size

        rows: list[list[str]] = []
        while True:
            if self.peek() != "|":
                break
            s = "|"
            await self.consume()
            while self.peek() not in ["\n", None]:
                s += self.peek() or ""
                await self.consume()
            if self.peek() == "\n":
                await self.consume()
            s = s.strip("|")
            rows.append([c.strip() for c in s.split("|")])
        # not enough rows
        if len(rows) < 2:
            self.emit("| " + " | ".join(rows[0]) + " |\n")
        # do some simple formatting
        cols = len(rows[0])
        col_widths = [0] * cols
        aligns: list[Literal["left", "right", "center"]] = ["left"] * cols
        for i, row in enumerate(rows):
            if i == 1:
                # check for alignment
                for j, c in enumerate(row):
                    if c.startswith(":") and c.endswith(":"):
                        aligns[j] = "center"
                    elif c.startswith(":"):
                        aligns[j] = "left"
                    elif c.endswith(":"):
                        aligns[j] = "right"
                continue
            for j, c in enumerate(row):
                col_widths[j] = max(col_widths[j], str_size(c))
        # print top border
        with self.state.style(dim=True):
            for j, c in enumerate(rows[0]):
                self.emit("╭" if j == 0 else "┬")
                self.emit("─" * (col_widths[j] + 2))
            self.emit("╮\n")
        # print the table
        for i, row in enumerate(rows):
            for j, c in enumerate(row):
                with self.state.style(dim=True):
                    self.emit("│" if i != 1 else ("├" if j == 0 else "┼"))
                if i == 1:
                    text = "─" * (col_widths[j] + 2)
                else:
                    s = str_size(c)
                    align = aligns[j] if i != 0 else "center"
                    match align:
                        case "left":
                            text = c + " " * (col_widths[j] - s)
                        case "right":
                            text = " " * (col_widths[j] - s) + c
                        case "center":
                            padding = col_widths[j] - s
                            text = " " * (padding // 2) + c
                            text += " " * (padding - padding // 2)
                    text = f" {text} "
                with self.state.style(dim=i == 1):
                    self.emit(text)
            with self.state.style(dim=True):
                self.emit("│\n" if i != 1 else "┤\n")
        # print bottom border
        with self.state.style(dim=True):
            for j, c in enumerate(rows[0]):
                self.emit("╰" if j == 0 else "┴")
                self.emit("─" * (col_widths[j] + 2))
            self.emit("╯\n")

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
                # Table
                case "|":
                    await self.parse_table()
                # Normal paragraph
                case _:
                    await self.parse_paragraph()
        self.emit("\x1b[0m")  # Reset all

    def __await__(self):
        return self.parse_doc().__await__()
