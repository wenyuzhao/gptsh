from dataclasses import dataclass, field
from .printer import StreamedMarkdownPrinter
from neongrid.style import STYLE, StyleScope


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


class InvalidState(Exception):
    def __init__(self, token: str):
        super().__init__(token)
        self.token = token


@dataclass
class InlineScope:
    state: StyleScope

    stack: list[Keyword] = field(default_factory=list)

    @property
    def last(self) -> str | None:
        return self.stack[-1].token if len(self.stack) > 0 else None

    @property
    def strike(self) -> bool:
        return self.last == "~~"

    @property
    def code(self) -> bool:
        return self.last == "`"

    def enter(self, kind: Keyword):
        match kind:
            case "`":
                self.state.enter(dim=True)
            case "~~":
                self.state.enter(strike=True)
            case _ if kind.is_bold():
                self.state.enter(bold=True, color=STYLE.highlight)
            case _ if kind.is_italic():
                self.state.enter(italic=True, color=STYLE.highlight)
            case _ if kind.is_bold_and_italic():
                self.state.enter(bold=True, italic=True, color=STYLE.highlight)
            case _:
                self.state.enter()
        self.stack.append(kind)

    def exit(self):
        self.stack.pop()
        self.state.exit()


class InlineTextPrinter:
    def __init__(self, p: StreamedMarkdownPrinter, table: bool = False):
        self.p = p
        self.terminator = ["\n", None]
        if table:
            self.terminator.append("|")

    def emit(self, s: str | None):
        if s is None:
            return
        self.p.emit(s)

    def peek(self):
        return self.p.peek()

    async def consume(self, n: int = 1):
        return await self.p.consume(n)

    async def check(self, s: str, eof: bool | None = None) -> bool:
        return await self.p.check(s, eof)

    async def parse_inline_unformatted(self):
        # Parse until another "`" or a newline, or EOF
        while not self.peek() in self.terminator:
            c = await self.p.consume()
            self.emit(c)

    async def parse_inline_code(self):
        self.emit("`")
        # Parse until another "`" or a newline, or EOF
        while not await self.check("`"):
            c = await self.p.consume()
            if c in self.terminator:
                return
            self.emit(c)
            if c == "\\":
                c = await self.p.consume()
                if c in self.terminator:
                    return
                self.emit(c)
        self.emit("`")
        await self.p.consume()

    async def get_next_token(self) -> str | Keyword | None:
        c = self.peek()
        if c in self.terminator:
            return None
        if c == "`":
            await self.consume()
            return Keyword("`")
        if c == "*":
            s = ""
            while self.peek() == "*":
                s += c
                await self.consume()
            return Keyword(s)
        if c == "_":
            s = ""
            while self.peek() == "_":
                s += c
                await self.consume()
            return Keyword(s)
        if c == "~" and await self.check("~~"):
            s = ""
            while self.peek() == "~":
                s += c
                await self.consume()
            return Keyword(s)
        if c == " " or c == "\t":
            s = ""
            while self.peek() == " " or self.peek() == "\t":
                s += c
                await self.consume()
            return s
        s = c or ""
        if c == "\\":
            await self.consume()
            c = self.peek()
            if c in self.terminator:
                return None if len(s) == 0 else s
            s += c or ""
            await self.consume()
        else:
            await self.consume()
        if len(s) == 0:
            return None
        return s

    def is_space_or_end(self, c: str | None) -> bool:
        if c is None:
            return True
        if c[0] in ["\n", " ", *self.terminator]:
            return True
        return False

    def is_end_or_non_alnum(self, c: str | None) -> bool:
        if c is None:
            return True
        if c[0] in ["\n", " ", *self.terminator]:
            return True
        return c[0].isalnum() is False

    async def parse_inline(self, consume_trailing_newline: bool = True):
        last_is_space = False
        start = True
        scope = InlineScope(self.p.state)

        while True:
            t = await self.get_next_token()
            curr_is_space = False

            if t is None:
                if consume_trailing_newline:
                    if self.peek() == "\n":
                        await self.consume()
                    self.emit("\n")
                break
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
                with self.p.state.style(dim=True):
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
                and not self.is_space_or_end(self.peek())
                and scope.last != t.token
            ):
                # Start bold or italics
                scope.enter(t)
                self.emit(t.token)
            elif (
                t.is_bold_or_italic()
                and (not last_is_space)
                and scope.last == t.token
                and self.is_end_or_non_alnum(self.peek())
            ):
                # End bold or italics
                self.emit(t.token)
                scope.exit()
            elif t.is_bold_or_italic():
                self.emit(t.token)
            else:
                # print(
                #     "Invalid token:", t.token, f"[{self.peek()}]", scope.last == t.token
                # )
                raise InvalidState(t.token)

            last_is_space = curr_is_space
            start = False
        while len(scope.stack) > 0:
            scope.exit()
