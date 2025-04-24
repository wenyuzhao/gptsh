import asyncio
from typing import Any, Coroutine

from .measure import text_display_width
from .style import Color

"""
Credit to https://github.com/briandowns/spinner
"""


async def __frames(
    frames: str | list[str],
    label: str = "Loading...",
    fps: int = 10,
    frames_per_color: int | None = None,
    update_label_color: bool = True,
):
    frames = list(c for c in frames) if isinstance(frames, str) else frames
    frame_width = text_display_width(frames[0])
    for c in frames:
        assert (
            text_display_width(c) == frame_width
        ), "All chars must have the same display width"
    count = 0
    label_w = text_display_width(label)
    length = frame_width + label_w + 1 + 2
    colors = [
        Color.RED,
        Color.GREEN,
        Color.YELLOW,
        Color.BLUE,
        Color.MAGENTA,
        Color.CYAN,
    ]
    color_index = 0
    frames_per_color = frames_per_color or len(frames)
    while True:
        try:
            current_color = colors[color_index]
            print(f"\x1b[{current_color.foreground}m", end="", flush=True)
            print(frames[count], end="", flush=True)
            if not update_label_color:
                print("\x1b[0m", end="", flush=True)
            print(" " + label, end="", flush=True)
            count += 1
            await asyncio.sleep(1.0 / fps)
            print("\b" * length, end="", flush=True)
            print(" " * length, end="", flush=True)
            print("\b" * length, end="", flush=True)
            if count == len(frames):
                count = 0
            if count % frames_per_color == 0:
                color_index += 1
                if color_index >= len(colors):
                    color_index = 0
        except asyncio.CancelledError:
            print("\b" * length, end="", flush=True)
            print(" " * length, end="", flush=True)
            print("\b" * length, end="", flush=True)
            print("\x1b[0m", end="", flush=True)
            break


def braille(label: str = "Loading..."):
    chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    return Loading(__frames(chars, label))


def breathing_cursor(label: str = "Loading..."):
    chars = "▉▊▋▌▍▎▏▎▍▌▋▊▉"
    return Loading(__frames(chars, label, update_label_color=False))


def clock(label: str = "Loading..."):
    chars = "🕐🕑🕒🕓🕔🕕🕖🕗🕘🕙🕚🕛"
    return Loading(__frames(chars, label))


def globe(label: str = "Loading..."):
    chars = "🌍🌎🌏"
    return Loading(__frames(chars, label, fps=5))


def kana(label: str = "Loading..."):
    chars = "ｦｧｨｩｪｫｬｭｮｯｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ"
    return Loading(__frames(chars, label, fps=10, frames_per_color=5))


class Loading:
    def __init__(self, fn: Coroutine[Any, Any, None]):
        self.__task = asyncio.create_task(fn)

    async def finish(self):
        self.__task.cancel()
        try:
            await self.__task
        except asyncio.CancelledError:
            pass
