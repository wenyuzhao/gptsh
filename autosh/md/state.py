from dataclasses import dataclass
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
