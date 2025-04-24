from dataclasses import dataclass, field
from io import StringIO
from typing import Literal, Optional, Protocol, TypeVar
from markdown_it import MarkdownIt
import sys
from markdown_it.token import Token

from . import measure
from .style import StyleScope, STYLE

_T = TypeVar("_T", contravariant=True)


class SupportsWrite(Protocol[_T]):
    def write(self, s: _T, /) -> object: ...


# stable
class SupportsFlush(Protocol):
    def flush(self) -> object: ...


class _SupportsWriteAndFlush(SupportsWrite[_T], SupportsFlush, Protocol[_T]): ...


def printmd(
    *values,
    sep=" ",
    end="\n",
    file: _SupportsWriteAndFlush[str] | None = None,
    flush: bool = False,
    raw: bool = False,
):
    """
    Prints the values to a stream, or to sys.stdout by default.

    **sep** - string inserted between values, default a space.

    **end** - string appended after the last value, default a newline.

    **file** - a file-like object (stream); defaults to the current sys.stdout.

    **flush** - whether to forcibly flush the stream.
    """
    if (
        raw
        or ((file == sys.stdout or file == sys.__stdout__) and not sys.stdout.isatty())
        or ((file == sys.stderr or file == sys.__stderr__) and not sys.stderr.isatty())
    ):
        # The user can't see the glowed output anyway
        # Fallback to default print
        print(*values, sep=sep, end=end, file=file, flush=flush)
        return
    # Parse and render markdown
    content = sep.join(str(value) for value in values)
    md = MarkdownIt("commonmark").enable(["strikethrough", "table", "blockquote"])
    tokens = md.parse(content)
    renderer = MDRenderer(tokens)
    renderer.render()
    print(renderer.get_rendered_content(), end=end, file=file, flush=flush)


@dataclass
class BlockNode:
    type: Literal[
        "inline",
        "paragraph",
        "blockquote",
        "heading",
        "ordered_list",
        "unordered_list",
        "list_item",
        "break",
        "code",
        "table",
    ]
    tag: str
    info: str | None = None
    children: list["BlockNode"] = field(default_factory=list)
    content: list[Token] | str | None = None
    table: Optional["Table"] = None


@dataclass
class Table:
    align: list[Literal["left", "center", "right"]] = field(default_factory=list)
    head: list[BlockNode] = field(default_factory=list)
    body: list[list[BlockNode]] = field(default_factory=list)


class MDRenderer:
    def __init__(self, tokens: list[Token]):
        self.tree: list[BlockNode] = BlockNodeParser(tokens).parse()
        self.indents: list[str] = []
        self.scope = StyleScope()
        self.i = 0

    def get_rendered_content(self) -> str:
        buf = self.scope.get_buffer()
        if buf is not None:
            return buf.getvalue()
        return ""

    def emit(self, s: str):
        self.scope.emit(s)

    def get_block_text(self, node: BlockNode) -> str:
        buf = self.scope._swap_buffer(StringIO())
        self.scope._disable_style()
        self.render_block(node)
        self.scope._enable_style()
        buf = self.scope._swap_buffer(buf)
        assert buf is not None
        return buf.getvalue()

    def render_inline(self, content: list[Token]):
        i = 0
        while i < len(content):
            token = content[i]
            match token.type:
                case "text":
                    self.emit(token.content)
                case "strong_open":
                    self.scope.enter(bold=True, color=STYLE.highlight)
                case "strong_close":
                    self.scope.exit()
                case "em_open":
                    self.scope.enter(italic=True, color=STYLE.highlight)
                case "em_close":
                    self.scope.exit()
                case "s_open":
                    self.scope.enter(strike=True)
                case "s_close":
                    self.scope.exit()
                case "link_open":
                    self.scope.enter(
                        underline=True,
                        color=STYLE.highlight,
                        dim=True,
                        bold=False,
                        italic=True,
                    )
                    i += 1
                    self.emit(str(token.attrs.get("href", "")))
                    while i < len(content) and content[i].type != "link_close":
                        i += 1
                    self.scope.exit()
                case "softbreak":
                    self.emit("\n")
                case "hardbreak":
                    self.emit("\n\n")
                case "code_inline":
                    self.scope.enter(dim=True)
                    self.emit(token.content)
                    self.scope.exit()
                case "image":
                    src = token.attrs.get("src")
                    with self.scope.style(color=STYLE.highlight):
                        with self.scope.style(dim=True):
                            self.emit(f"[")
                        self.emit(f"🏞️  ")
                        self.emit(token.content)
                        with self.scope.style(dim=True):
                            self.emit(f"](")
                            with self.scope.style(underline=True, italic=True):
                                self.emit(str(src))
                            self.emit(")")
                case _:
                    # print(token)
                    # print("next", content[i + 1] if i + 1 < len(content) else None)
                    self.emit(token.content)
            i += 1

    def render_block(self, node: BlockNode):
        match node.type:
            case "inline":
                assert isinstance(node.content, list)
                self.emit("".join(self.indents))
                self.render_inline(node.content)
            case "break":
                w = min(measure.viewpoint().cols, 80)
                self.emit("─" * w)
            case "code":
                assert isinstance(node.content, str)
                w = measure.viewpoint().cols
                if w <= 4:
                    with self.scope.style(dim=True, bold=False, italic=False):
                        self.emit("```\n")
                        self.emit(node.content)
                        if not node.content.endswith("\n"):
                            self.emit("\n")
                        self.emit("```")
                else:
                    content_w = w - 4
                    content_size, rows = measure.measure_text(node.content, content_w)
                    with self.scope.style(dim=True, bold=False, italic=False):
                        self.emit("╭" + "─" * (content_size.cols + 2) + "╮\n")
                        for row in rows:
                            self.emit(
                                "│ "
                                + row
                                + " "
                                * (content_size.cols - measure.text_display_width(row))
                                + " │\n"
                            )
                        self.emit("╰" + "─" * (content_size.cols + 2) + "╯")

            case "paragraph":
                self.render_nodes(node.children)
            case "blockquote":
                self.scope.enter(dim=True)
                self.indents.append("┃ ")
                self.render_nodes(node.children)
                self.indents.pop()
                self.scope.exit()
            case "heading":
                match node.tag:
                    case "h1":
                        self.scope.enter(bold=True, bg=STYLE.highlight)
                        self.emit(" ")
                    case "h2":
                        self.scope.enter(
                            bold=True, underline=True, color=STYLE.highlight
                        )
                    case "h3":
                        self.scope.enter(bold=True, italic=True, color=STYLE.highlight)
                    case "h4":
                        self.scope.enter(bold=True, color=STYLE.highlight)
                    case _:
                        self.scope.enter(bold=True)
                self.render_nodes(node.children)
                if node.tag == "h1":
                    self.emit(" ")
                self.scope.exit()
            case "ordered_list":
                if len(node.children) == 0:
                    self.emit("".join(self.indents))
                    self.emit("1. \n")
                else:
                    base = 1
                    for i, list_item in enumerate(node.children):
                        if i == 0 and list_item.info is not None:
                            base = int(list_item.info)
                        ordinal = base + i
                        for j, x in enumerate(list_item.children):
                            self.indents.append(f"{ordinal}. " if j == 0 else "   ")
                            self.render_block(x)
                            if j != len(list_item.children) - 1:
                                self.emit("\n")
                            self.indents.pop()
                        if i != len(node.children) - 1:
                            self.emit("\n")
            case "unordered_list":
                if len(node.children) == 0:
                    self.emit("".join(self.indents))
                    self.emit(" • \n")
                else:
                    for i, list_item in enumerate(node.children):
                        for j, x in enumerate(list_item.children):
                            self.indents.append(" • " if j == 0 else "   ")
                            self.render_block(x)
                            if j != len(list_item.children) - 1:
                                self.emit("\n")
                            self.indents.pop()
                        if i != len(node.children) - 1:
                            self.emit("\n")
            case "list_item":
                if node.info is not None:
                    self.emit(f"[{node.info}] ")
                for i, x in enumerate(node.children):
                    self.indents.append("   " if i == 0 else "     ")
                    self.render_block(x)
                    if i != len(node.children) - 1:
                        self.emit("\n")
                    self.indents.pop()
            case "table":
                assert isinstance(node.table, Table)
                column_sizes = []
                cells: list[list[str]] = []
                # Get header sizes
                row = []
                for i, x in enumerate(node.table.head):
                    s = self.get_block_text(x)
                    row.append(s)
                    cols = measure.text_display_width(s)
                    column_sizes.append(cols)
                cells.append(row)
                # Get body sizes
                for row in node.table.body:
                    r = []
                    for i, x in enumerate(row):
                        s = self.get_block_text(x)
                        r.append(s)
                        cols = measure.text_display_width(s)
                        column_sizes[i] = max(column_sizes[i], cols)
                    cells.append(r)
                # Adjust column sizes
                cols = column_sizes
                # Calculate strings
                table: list[list[BlockNode]] = [[]]
                for i, x in enumerate(node.table.head):
                    table[0].append(x)
                for i, row in enumerate(node.table.body):
                    table.append([])
                    for j, x in enumerate(row):
                        table[i + 1].append(x)
                # Print table
                # 1. top border
                with self.scope.style(dim=True):
                    self.emit("╭")
                    for i, c in enumerate(cols):
                        if i != 0:
                            self.emit("┬")
                        self.emit("─" * (c + 2))
                    self.emit("╮\n")
                # 2. rows
                for i, row in enumerate(table):
                    with self.scope.style(dim=True):
                        self.emit("│ ")
                    for j, x in enumerate(row):
                        s = cells[i][j]
                        gap = cols[j] - measure.text_display_width(s)
                        align = node.table.align[j]
                        if i == 0:
                            self.scope.enter(bold=True)
                        if align == "right":
                            self.emit(" " * gap)
                            self.render_block(x)
                        elif align == "center":
                            lpad = gap // 2
                            rpad = gap - lpad
                            self.emit(" " * lpad)
                            self.render_block(x)
                            self.emit(" " * rpad)
                        else:
                            self.render_block(x)
                            self.emit(" " * gap)
                        if i == 0:
                            self.scope.exit()
                        if j != len(row) - 1:
                            with self.scope.style(dim=True):
                                self.emit(" │ ")
                    with self.scope.style(dim=True):
                        self.emit(" │\n")
                    # separator
                    if i == 0:
                        with self.scope.style(dim=True):
                            self.emit("├")
                            for i, c in enumerate(cols):
                                if i != 0:
                                    self.emit("┼")
                                self.emit("─" * (c + 2))
                            self.emit("┤\n")
                # 3. bottom border
                with self.scope.style(dim=True):
                    self.emit("╰")
                    for i, c in enumerate(cols):
                        if i != 0:
                            self.emit("┴")
                        self.emit("─" * (c + 2))
                    self.emit("╯")
            case _:
                raise ValueError(f"Unknown block type: {node.type}")

    def render_nodes(self, nodes: list[BlockNode]):
        for i, node in enumerate(nodes):
            if i == len(nodes) - 1:
                self.render_block(node)
            else:
                self.render_block(node)
                self.emit(f"\n{''.join(self.indents)}\n")

    def render(self):
        self.render_nodes(self.tree)


class BlockNodeParser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0

    def parse_block(self) -> BlockNode:
        t = self.tokens[self.i]
        match t.type:
            case "inline":
                self.i += 1
                return BlockNode(type="inline", tag=t.tag, content=t.children)
            case "paragraph_open":
                self.i += 1
                node = BlockNode(type="paragraph", tag=t.tag)
                while self.tokens[self.i].type != "paragraph_close":
                    node.children.append(self.parse_block())
                self.i += 1
                return node
            case "blockquote_open":
                self.i += 1
                node = BlockNode(type="blockquote", tag=t.tag)
                while self.tokens[self.i].type != "blockquote_close":
                    node.children.append(self.parse_block())
                self.i += 1
                return node
            case "heading_open":
                self.i += 1
                node = BlockNode(type="heading", tag=t.tag)
                while self.tokens[self.i].type != "heading_close":
                    node.children.append(self.parse_block())
                self.i += 1
                return node
            case "ordered_list_open":
                self.i += 1
                node = BlockNode(type="ordered_list", tag=t.tag)
                while self.tokens[self.i].type != "ordered_list_close":
                    node.children.append(self.parse_block())
                self.i += 1
                return node
            case "bullet_list_open":
                self.i += 1
                node = BlockNode(type="unordered_list", tag=t.tag)
                while self.tokens[self.i].type != "bullet_list_close":
                    node.children.append(self.parse_block())
                self.i += 1
                return node
            case "list_item_open":
                self.i += 1
                node = BlockNode(type="list_item", tag=t.tag, info=t.info)
                while self.tokens[self.i].type != "list_item_close":
                    node.children.append(self.parse_block())
                self.i += 1
                return node
            case "hr":
                self.i += 1
                return BlockNode(type="break", tag=t.tag)
            case "code_block" | "fence":
                self.i += 1
                return BlockNode(type="code", tag=t.tag, content=t.content, info=t.info)
            case "table_open":
                self.i += 1
                table = Table()
                # Parse header
                self.i += 2  # skip thead_open, tr_open
                while self.tokens[self.i].type == "th_open":
                    style = self.tokens[self.i].attrs.get("style")
                    match style:
                        case "text-align:right":
                            table.align.append("right")
                        case "text-align:center":
                            table.align.append("center")
                        case _:
                            table.align.append("left")
                    self.i += 1
                    node = self.parse_block()
                    table.head.append(node)
                    self.i += 1  # th_close
                self.i += 2  # tr_close, thead_close
                # Parse body
                self.i += 1  # tbody_open
                while self.tokens[self.i].type == "tr_open":
                    self.i += 1
                    row = []
                    while self.tokens[self.i].type == "td_open":
                        self.i += 1
                        node = self.parse_block()
                        row.append(node)
                        self.i += 1  # td_close
                    table.body.append(row)
                    self.i += 1  # tr_close
                self.i += 1  # tbody_close
                self.i += 1  # table_close
                return BlockNode(
                    type="table",
                    tag=t.tag,
                    table=table,
                )
            case _:
                print(t)
                raise ValueError(f"Unknown token type: {t.type}")

    def parse(self) -> list[BlockNode]:
        nodes = []
        while self.i < len(self.tokens):
            nodes.append(self.parse_block())
        return nodes
