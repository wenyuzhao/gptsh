from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, StrEnum
from io import StringIO


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

    @property
    def name(self) -> str:
        return self._name_.lower()


@dataclass
class Style:
    highlight: Color = Color.MAGENTA

    input_color: Color | None = Color.CYAN
    confirm_color: Color | None = Color.CYAN


STYLE = Style()  # Default style


def set_style(style: Style):
    global STYLE
    STYLE = style


ESC = "\x1b"


class Ctrl(StrEnum):
    bold = ESC + "[1m"
    dim = ESC + "[2m"
    italic = ESC + "[3m"
    underline = ESC + "[4m"
    # blink = ESC + "[5m"
    # reverse = ESC + "[7m"
    # hidden = ESC + "[8m"
    strike = ESC + "[9m"

    reset_all = ESC + "[0m"
    reset_bold_and_dim = ESC + "[22m"
    reset_italic = ESC + "[23m"
    reset_underline = ESC + "[24m"
    reset_strike = ESC + "[29m"

    @staticmethod
    def color(c: Color):
        return ESC + f"[{c.foreground}m"

    @staticmethod
    def bg(c: Color):
        return ESC + f"[{c.background}m"


@dataclass
class StyleScopeState:
    is_bold: bool = False
    is_dim: bool = False
    is_italic: bool = False
    is_underline: bool = False
    is_strike: bool = False
    foreground_color: Color | None = None
    background_color: Color | None = None
    cursor_visible: bool = True

    def clone(self):
        return StyleScopeState(
            is_bold=self.is_bold,
            is_dim=self.is_dim,
            is_italic=self.is_italic,
            is_underline=self.is_underline,
            is_strike=self.is_strike,
            foreground_color=self.foreground_color,
            background_color=self.background_color,
            cursor_visible=self.cursor_visible,
        )


class StyleScope:
    __stack: list[StyleScopeState]

    def __init__(self, buf: StringIO | None = None) -> None:
        self.__stack = [StyleScopeState()]
        self.__buf = buf
        self.__raw_mode = False

    def _swap_buffer(self, buf: StringIO | None) -> StringIO | None:
        old_buf = self.__buf
        self.__buf = buf
        return old_buf

    def _restore_buffer(self, buf: StringIO | None):
        if self.__buf is not None:
            self.__buf.close()
        self.__buf = buf

    def _disable_style(self):
        self.__raw_mode = True

    def _enable_style(self):
        self.__raw_mode = False

    def emit(self, text: str):
        if self.__buf is not None:
            self.__buf.write(text)
        else:
            print(text, end="", flush=True)

    def get_buffer(self) -> StringIO | None:
        return self.__buf

    def enter(
        self,
        bold: bool | None = None,
        dim: bool | None = None,
        italic: bool | None = None,
        underline: bool | None = None,
        strike: bool | None = None,
        color: Color | None = None,
        bg: Color | None = None,
        cursor_visible: bool | None = None,
    ):
        assert len(self.__stack) > 0
        state = self.__stack[-1].clone()

        if bold is not None:
            state.is_bold = bold
        if dim is not None:
            state.is_dim = dim
        if italic is not None:
            state.is_italic = italic
        if underline is not None:
            state.is_underline = underline
        if strike is not None:
            state.is_strike = strike
        if color is not None:
            state.foreground_color = color
        if bg is not None:
            state.background_color = bg
        if cursor_visible is not None:
            state.cursor_visible = cursor_visible
        self.__apply_all(state)
        self.__stack.append(state)

    def exit(self):
        assert len(self.__stack) > 1
        self.__stack.pop()
        self.__apply_all(self.__stack[-1])

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
        cursor_visible: bool | None = None,
    ):
        self.enter(
            bold=bold,
            dim=dim,
            italic=italic,
            underline=underline,
            strike=strike,
            color=color,
            bg=bg,
            cursor_visible=cursor_visible,
        )
        yield
        self.exit()

    def __apply_all(self, state: StyleScopeState):
        if not self.__raw_mode:
            self.emit(f"{ESC}[0m")
        codes = []
        if state.is_bold:
            codes.append(1)
        if state.is_dim:
            codes.append(2)
        if state.is_italic:
            codes.append(3)
        if state.is_underline:
            codes.append(4)
        if state.is_strike:
            codes.append(9)
        if state.foreground_color:
            codes.append(state.foreground_color.foreground)
        if state.background_color:
            codes.append(state.background_color.background)

        if not self.__raw_mode:
            codes = ";".join(map(str, codes))
            if len(codes) > 0:
                self.emit(f"{ESC}[{codes}m")
            if not state.cursor_visible:
                self.emit(f"{ESC}[?25l")
