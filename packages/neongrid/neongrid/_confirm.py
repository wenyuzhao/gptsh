from contextlib import contextmanager
import sys
import termios
import tty
from neongrid.style import ESC, STYLE, StyleScope, Color


@contextmanager
def raw_mode():
    fd = sys.stdin.fileno()
    original_attrs = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, original_attrs)


class Confirm:
    def __init__(self, default: bool = True):
        self.__start_pos = 0
        self.__active = default
        self.__yes_label = " ✔ YES "
        self.__no_label = " ✘ NO "
        self.scope = StyleScope()

    def get_cursor_pos(self):
        print(f"{ESC}[6n", end="", flush=True)
        s = ""
        while True:
            ch = sys.stdin.read(1)
            s += ch
            if ch == "R":
                break
        # print(s, end="", flush=True)
        s = s[2:-1].split(";")
        col = int(s[1])
        return col

    def getch(self):
        ch = sys.stdin.read(1)
        if ch == "\x03":
            raise KeyboardInterrupt()
        if ch == "\x04":
            raise EOFError()
        return ch

    def switch_left(self):
        if self.__active:
            return
        self.__active = True
        self.render_options()

    def switch_right(self):
        if not self.__active:
            return
        self.__active = False
        self.render_options()

    def render_options(self):
        print(f"{ESC}[{self.__start_pos}G{ESC}[0K", end="", flush=True)
        if self.__active:
            with self.scope.style(bold=True, bg=Color.BRIGHT_GREEN):
                print(self.__yes_label, end="", flush=True)
            with self.scope.style(bold=True, color=Color.BRIGHT_RED):
                print(self.__no_label, end="", flush=True)
        else:
            with self.scope.style(bold=True, color=Color.BRIGHT_GREEN):
                print(self.__yes_label, end="", flush=True)
            with self.scope.style(bold=True, bg=Color.BRIGHT_RED):
                print(self.__no_label, end="", flush=True)

    def render_final_result(self):
        print(f"{ESC}[{self.__start_pos}G{ESC}[0K", end="", flush=True)
        if self.__active:
            with self.scope.style(bold=True, bg=Color.BRIGHT_GREEN):
                print(self.__yes_label, end="", flush=True)
        else:
            with self.scope.style(bold=True, bg=Color.BRIGHT_RED):
                print(self.__no_label, end="", flush=True)

    def run(self):
        with self.scope.style(cursor_visible=False):
            with raw_mode():
                self.__start_pos = self.get_cursor_pos()
                self.render_options()
                while True:
                    ch = self.getch()

                    if ch == "\x0d":  # Enter key
                        break

                    if ch == ESC:
                        s = "E"
                        # control characters
                        ch = self.getch()
                        s += ch
                        if ch == "[":
                            ch = self.getch()
                            s += ch
                            if ch == "C" or ch == "B":
                                self.switch_right()
                            if ch == "D" or ch == "A":
                                self.switch_left()
                    elif ch in ["a", "w", "y", "H", "t"]:
                        self.switch_left()
                    elif ch in ["d", "s", "n", "F", "f"]:
                        self.switch_right()

                self.render_final_result()
        print()
        return self.__active


def confirm(prompt: str, default=True) -> bool:
    scope = StyleScope()
    with scope.style(bold=True, color=STYLE.confirm_color):
        prompt = prompt.strip() + " "
        print(prompt, end="", flush=True)
    return Confirm(default=default).run()
